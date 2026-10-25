"""Allow-listed desktop actions. AI output can never trigger anything outside this module.

Typing uses clipboard paste into the field the *user* focused — never clicks at coordinates
guessed from a screenshot. Every action checks the cancel flag and the foreground window, and
PyAutoGUI's fail-safe (slam the mouse into a screen corner) aborts instantly.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from app.error_handler import AgentError, ErrorCategory
from app.form_mode import FillStep

APP_WINDOW_MARKER = "One Click"   # must appear in every One Click window title (self-type guard)
MAX_VALUE_LENGTH = 5000


class Action(str, Enum):
    COPY = "copy"
    PASTE_INTO_FOCUSED = "paste_into_focused"
    TAB = "tab"


ALLOWED_ACTIONS = frozenset(Action)


@dataclass(frozen=True)
class FillOutcome:
    label: str
    status: str   # "entered (verify on screen)" | "skipped" | "failed: ..." | "not reached"


@dataclass(frozen=True)
class ClickFillStep:
    """One feedback target: click a start point, then either arrow to a choice or type text."""
    label: str
    xnorm: float       # 0-1000, relative to the captured image
    ynorm: float
    arrow: str = ""    # "right" | "down" | "" — direction to move within a radio group
    steps: int = 0     # number of arrow presses (= chosen option index)
    text: str = ""     # for comment boxes: paste this after clicking


def copy_to_clipboard(text: str) -> None:
    import pyperclip
    try:
        pyperclip.copy(text)
    except Exception as exc:
        raise AgentError(ErrorCategory.AUTOMATION, "Could not access the clipboard.",
                         "Select the text in the results panel and copy it manually.") from exc


def _active_window_title() -> str | None:
    try:
        import pyautogui
        return pyautogui.getActiveWindowTitle()
    except Exception:
        return None


def _validate(action: Action, value: str = "") -> None:
    if action not in ALLOWED_ACTIONS:
        raise AgentError(ErrorCategory.AUTOMATION, f"Action '{action}' is not allowed.")
    if len(value) > MAX_VALUE_LENGTH:
        raise AgentError(ErrorCategory.AUTOMATION, "Value is too long to enter safely.")


class AutomationService:
    def __init__(self):
        self.cancel = threading.Event()

    def _check_target(self, expected_title: str | None) -> None:
        if self.cancel.is_set():
            raise AgentError(ErrorCategory.CANCELLED, "Stopped by user.")
        title = _active_window_title()
        if title and APP_WINDOW_MARKER in title:
            raise AgentError(ErrorCategory.AUTOMATION,
                             "One Click itself has focus — nothing was typed.",
                             "Click into the target field during the countdown.")
        if expected_title is not None and title != expected_title:
            raise AgentError(ErrorCategory.AUTOMATION,
                             "The target window changed — automation stopped.",
                             "Refocus the field and try again.")

    def _paste(self, value: str) -> None:
        import pyautogui
        import pyperclip
        _validate(Action.PASTE_INTO_FOCUSED, value)
        pyperclip.copy(value)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.15)

    def run_fill(self, steps: list[FillStep],
                 progress: Callable[[str], None] = lambda _m: None) -> list[FillOutcome]:
        """Paste approved values into consecutive fields, starting at the focused one."""
        import pyautogui
        import pyperclip

        pyautogui.FAILSAFE = True
        self.cancel.clear()
        outcomes: list[FillOutcome] = []
        try:
            saved_clipboard = pyperclip.paste()
        except Exception:
            saved_clipboard = None
        try:
            self._check_target(None)
            target = _active_window_title()
            for index, step in enumerate(steps):
                try:
                    self._check_target(target)
                    if step.fill:
                        self._paste(step.value)
                        outcomes.append(FillOutcome(step.label, "entered (verify on screen)"))
                        progress(f"Entered “{step.label}”")
                    else:
                        outcomes.append(FillOutcome(step.label, "skipped"))
                    if index < len(steps) - 1:
                        _validate(Action.TAB)
                        pyautogui.press("tab")
                        time.sleep(0.1)
                except pyautogui.FailSafeException:
                    raise AgentError(ErrorCategory.CANCELLED, "Fail-safe triggered (mouse in corner).")
                except AgentError as err:
                    outcomes.append(FillOutcome(step.label, f"failed: {err.message}"))
                    outcomes += [FillOutcome(s.label, "not reached") for s in steps[index + 1:]]
                    return outcomes
                except Exception as exc:
                    outcomes.append(FillOutcome(step.label, f"failed: {type(exc).__name__}"))
                    outcomes += [FillOutcome(s.label, "not reached") for s in steps[index + 1:]]
                    return outcomes
        except AgentError as err:
            done = {o.label for o in outcomes}
            outcomes += [FillOutcome(s.label, f"not reached ({err.message})")
                         for s in steps if s.label not in done]
        finally:
            if saved_clipboard is not None:
                try:
                    pyperclip.copy(saved_clipboard)
                except Exception:
                    pass
        return outcomes

    def run_click_fill(self, steps: list[ClickFillStep], region: tuple | None,
                       progress: Callable[[str], None] = lambda _m: None) -> list[FillOutcome]:
        """Feedback auto-fill: click each first option then arrow to the choice, or type a comment.

        Coordinates are normalized 0-1000 over the captured image; `region` (x,y,w,h in screen
        pixels) or the full screen maps them back to where to click.
        """
        import pyautogui
        import pyperclip

        pyautogui.FAILSAFE = True
        self.cancel.clear()
        outcomes: list[FillOutcome] = []
        try:
            saved_clipboard = pyperclip.paste()
        except Exception:
            saved_clipboard = None
        try:
            screen_w, screen_h = pyautogui.size()
            base_l, base_t, base_w, base_h = region if region else (0, 0, screen_w, screen_h)
            for step in steps:
                if self.cancel.is_set():
                    raise AgentError(ErrorCategory.CANCELLED, "Stopped by user.")
                x = int(min(max(base_l + step.xnorm / 1000.0 * base_w, 0), screen_w - 1))
                y = int(min(max(base_t + step.ynorm / 1000.0 * base_h, 0), screen_h - 1))
                try:
                    pyautogui.moveTo(x, y, duration=0.12)
                    pyautogui.click()
                    time.sleep(0.12)
                    if step.text:
                        self._paste(step.text)
                        outcomes.append(FillOutcome(step.label, "entered: comment typed (verify on screen)"))
                    else:
                        for _ in range(max(step.steps, 0)):
                            if self.cancel.is_set():
                                raise AgentError(ErrorCategory.CANCELLED, "Stopped by user.")
                            pyautogui.press(step.arrow or "right")
                            time.sleep(0.08)
                        outcomes.append(FillOutcome(
                            step.label, f"entered: option #{step.steps + 1} selected (verify on screen)"))
                    progress(f"Filled “{step.label}”")
                except pyautogui.FailSafeException:
                    self.cancel.set()   # so an outer auto-run loop also stops
                    raise AgentError(ErrorCategory.CANCELLED, "Fail-safe triggered (mouse in corner).")
        except AgentError as err:
            done = {o.label for o in outcomes}
            outcomes += [FillOutcome(s.label, f"not reached ({err.message})")
                         for s in steps if s.label not in done]
        finally:
            if saved_clipboard is not None:
                try:
                    pyperclip.copy(saved_clipboard)
                except Exception:
                    pass
        return outcomes

    def scroll(self, clicks: int) -> None:
        """Scroll the wheel (negative = down) over the screen centre to reveal more of a form."""
        import pyautogui
        try:
            w, h = pyautogui.size()
            pyautogui.moveTo(w // 2, h // 2)
            pyautogui.scroll(clicks)
        except Exception:
            pass

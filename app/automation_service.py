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

APP_WINDOW_MARKER = "CHEATER.exe"
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
                             "CHEATER.exe itself has focus — nothing was typed.",
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

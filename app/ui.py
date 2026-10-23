"""CustomTkinter desktop UI. Owns widgets only; all agent work happens in AgentController.

Background threads never touch widgets: they put AgentEvent objects on `self.events`, which
`_poll_events` drains on the Tk main loop.
"""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from app import practice_mode, theme as T
from app.activity_logger import ActivityLogger, LogEntry
from app.agent_controller import AgentController, AgentEvent, AgentState
from app.automation_service import AutomationService, copy_to_clipboard
from app.config import LOG_DIR, AppConfig, AgentSettings, save_settings
from app.error_handler import AgentError, ErrorCategory
from app.form_mode import FillStep, can_fill, default_approval, is_sensitive, plan_sequential_fill
from app.gemini_service import create_service
from app.modes import MODES, ModeContext
from app.response_models import FeedbackResult, FormResult, PracticeResult
from app.screenshot_service import Region, ScreenshotService

STATE_TEXT = {
    AgentState.IDLE: ("Ready", "Choose a mode, then Capture Once or Start Agent."),
    AgentState.RUNNING: ("Monitoring screen", "Sampling locally; only meaningful changes are "
                                              "sent to Gemini."),
    AgentState.PROCESSING: ("Analyzing with Gemini", "Waiting for a structured response…"),
    AgentState.PAUSED: ("Paused", "No new captures. Resume to continue monitoring."),
    AgentState.WAITING_FOR_REVIEW: ("Result ready for review", "Check the result before you "
                                                               "copy or fill anything."),
    AgentState.ERROR: ("Something went wrong", "See the error above the results. The app is "
                                               "still running — Retry or recapture."),
    AgentState.STOPPED: ("Stopped", "Agent stopped. Start again whenever you are ready."),
}
COUNTDOWN_S = 3


class CheaterApp(ctk.CTk):
    def __init__(self, config: AppConfig):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=T.BG)
        self.title("CHEATER.exe — The One-Click Agent")
        self.geometry("1280x820")
        self.minsize(1040, 680)
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "app" / "icon.ico"
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass  # cosmetic only

        self.config_data = config
        self.events: queue.Queue = queue.Queue()
        self.logger = ActivityLogger(LOG_DIR)
        self.logger.add_listener(lambda entry: self.events.put(AgentEvent("log", data=entry)))
        self.service = create_service(config)
        self.screens = ScreenshotService()
        self.controller = AgentController(self.service, self.screens, self.logger,
                                          config.settings, self.events)
        self.automation = AutomationService()

        self._closing = False
        self._filling = False
        self._gemini_ok = config.problem is None
        self._mode_inputs = {key: "" for key in MODES}
        self._result = None
        self._result_meta: dict = {}
        self._form_rows: list[tuple] = []
        self._wrap_labels: list[ctk.CTkLabel] = []
        self._current_task: int | None = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_left()
        self._build_right()
        self._build_footer()

        self.bind("<Configure>", self._on_configure, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._select_mode("practice", initial=True)
        self._render_empty()
        self._apply_state(AgentState.IDLE)
        self.after(80, self._poll_events)

        self.logger.ok("Application started.")
        if config.mock_mode:
            self.logger.warn(f"MOCK MODE — results are canned, not real AI "
                             f"(scenario: {config.mock_scenario}).")
        if config.problem:
            self.logger.error(config.problem)
            self._show_error_banner(AgentError(ErrorCategory.CONFIG, config.problem))
        else:
            threading.Thread(target=self._verify_gemini, daemon=True).start()

    # ================================================================== layout
    def _card(self, master, **kw) -> ctk.CTkFrame:
        opts = dict(fg_color=T.CARD, corner_radius=T.RADIUS, border_width=1, border_color=T.BORDER)
        opts.update(kw)
        return ctk.CTkFrame(master, **opts)

    def _caption(self, master, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(master, text=text, font=T.font(11, "bold"), text_color=T.TEXT_DIM,
                            anchor="w")

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=T.BG, height=72)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=T.PAD, pady=(T.PAD, 4))
        header.grid_columnconfigure(1, weight=1)

        badge = ctk.CTkLabel(header, text="⚡", width=46, height=46, corner_radius=T.RADIUS,
                             fg_color=T.ACCENT, text_color=T.ACCENT_TEXT, font=T.font(22, "bold"))
        badge.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(header, text="CHEATER.exe", font=T.font(22, "bold"), text_color=T.TEXT,
                     anchor="w").grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(header, text="THE ONE-CLICK AGENT  ·  one click, one agent, less busywork",
                     font=T.font(11), text_color=T.TEXT_MUTED, anchor="w"
                     ).grid(row=1, column=1, sticky="nw")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, sticky="e")
        if self.service.is_mock:
            ctk.CTkLabel(right, text="  MOCK MODE — NOT REAL AI  ", corner_radius=T.RADIUS_SM,
                         fg_color=T.WARNING, text_color="#2A1A00", font=T.font(11, "bold"),
                         height=30).pack(side="left", padx=(0, 10))
        self.status_pill = ctk.CTkLabel(right, text="● READY", corner_radius=15, height=30,
                                        width=130, fg_color=T.SURFACE, font=T.font(12, "bold"))
        self.status_pill.pack(side="left", padx=(0, 10))
        ctk.CTkButton(right, text="⚙  Settings", width=110,
                      command=self._open_settings, **T.secondary_button()).pack(side="left")

    def _build_left(self) -> None:
        left = ctk.CTkScrollableFrame(self, fg_color=T.BG, width=372,
                                      scrollbar_button_color=T.SURFACE,
                                      scrollbar_button_hover_color=T.BORDER)
        left.grid(row=1, column=0, sticky="nsw", padx=(T.PAD - 4, 6), pady=6)
        left.grid_columnconfigure(0, weight=1)
        row = 0

        self._caption(left, "MODE").grid(row=row, column=0, sticky="w", padx=4); row += 1
        self.mode_cards: dict[str, dict] = {}
        for key, spec in MODES.items():
            card = self._card(left, fg_color=T.CARD, cursor="hand2")
            card.grid(row=row, column=0, sticky="ew", pady=3, padx=2); row += 1
            card.grid_columnconfigure(1, weight=1)
            icon = ctk.CTkLabel(card, text=spec.icon, width=34, height=34, corner_radius=9,
                                fg_color=T.SURFACE, text_color=T.ACCENT, font=T.font(18, "bold"))
            icon.grid(row=0, column=0, rowspan=2, padx=10, pady=8)
            title = ctk.CTkLabel(card, text=spec.title, font=T.font(14, "bold"),
                                 text_color=T.TEXT, anchor="w")
            title.grid(row=0, column=1, sticky="sw", pady=(8, 0))
            desc = ctk.CTkLabel(card, text=spec.description, font=T.font(11),
                                text_color=T.TEXT_MUTED, anchor="w")
            desc.grid(row=1, column=1, sticky="nw", pady=(0, 8))
            for widget in (card, icon, title, desc):
                widget.bind("<Button-1>", lambda _e, k=key: self._select_mode(k))
            self.mode_cards[key] = dict(card=card, icon=icon)

        # controls
        controls = ctk.CTkFrame(left, fg_color="transparent")
        controls.grid(row=row, column=0, sticky="ew", pady=(8, 2), padx=2); row += 1
        controls.grid_columnconfigure((0, 1), weight=1)
        self.start_btn = ctk.CTkButton(controls, text="▶  Start Agent", command=self._start,
                                       **T.primary_button(height=44, font=T.font(14, "bold")))
        self.start_btn.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.pause_btn = ctk.CTkButton(controls, text="⏸  Pause", command=self._pause_resume,
                                       **T.secondary_button())
        self.pause_btn.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=3)
        self.stop_btn = ctk.CTkButton(controls, text="■  Stop", command=self._stop,
                                      **T.danger_button())
        self.stop_btn.grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=3)
        self.once_btn = ctk.CTkButton(controls, text="◎  Capture Once", command=self._capture_once,
                                      **T.secondary_button(text_color=T.ACCENT))
        self.once_btn.grid(row=2, column=0, sticky="ew", padx=(0, 3), pady=3)
        self.preview_btn = ctk.CTkButton(controls, text="🖼  Preview", command=self._preview,
                                         **T.secondary_button())
        self.preview_btn.grid(row=2, column=1, sticky="ew", padx=(3, 0), pady=3)
        self.retry_btn = ctk.CTkButton(controls, text="↻  Retry", command=self._retry,
                                       **T.secondary_button())
        self.retry_btn.grid(row=3, column=0, sticky="ew", padx=(0, 3), pady=3)
        self.clear_btn = ctk.CTkButton(controls, text="✕  Clear Results", command=self._clear,
                                       **T.secondary_button())
        self.clear_btn.grid(row=3, column=1, sticky="ew", padx=(3, 0), pady=3)
        # status
        status = self._card(left)
        status.grid(row=row, column=0, sticky="ew", pady=4, padx=2); row += 1
        status.grid_columnconfigure(0, weight=1)
        self._caption(status, "AGENT STATUS").grid(row=0, column=0, sticky="ew", padx=12,
                                                   pady=(10, 0))
        self.op_label = ctk.CTkLabel(status, text="Ready", font=T.font(15, "bold"),
                                     text_color=T.TEXT, anchor="w")
        self.op_label.grid(row=1, column=0, sticky="ew", padx=12)
        self.op_detail = ctk.CTkLabel(status, text="", font=T.font(11), text_color=T.TEXT_MUTED,
                                      anchor="w", justify="left", wraplength=320)
        self.op_detail.grid(row=2, column=0, sticky="ew", padx=12)
        self.progress = ctk.CTkProgressBar(status, height=6, fg_color=T.SURFACE,
                                           progress_color=T.ACCENT, mode="determinate")
        self.progress.set(0)
        self.progress.grid(row=3, column=0, sticky="ew", padx=12, pady=8)
        self.task_label = ctk.CTkLabel(status, text="Task: —   ·   Last success: —",
                                       font=T.font(11), text_color=T.TEXT_DIM, anchor="w")
        self.task_label.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 10))

        # mode-specific input
        input_card = self._card(left)
        input_card.grid(row=row, column=0, sticky="ew", pady=4, padx=2); row += 1
        input_card.grid_columnconfigure(0, weight=1)
        self.input_label = ctk.CTkLabel(input_card, text="", font=T.font(12, "bold"),
                                        text_color=T.TEXT, anchor="w")
        self.input_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        self.input_hint = ctk.CTkLabel(input_card, text="", font=T.font(11), anchor="w",
                                       text_color=T.TEXT_DIM, justify="left", wraplength=320)
        self.input_hint.grid(row=1, column=0, sticky="ew", padx=12)
        self.input_box = ctk.CTkTextbox(input_card, height=70, fg_color=T.SURFACE,
                                        border_color=T.BORDER, border_width=1,
                                        text_color=T.TEXT, font=T.font(12), wrap="word")
        self.input_box.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 8))
        self.input_box.bind("<KeyRelease>", lambda _e: self._sync_context())
        self.study_var = tk.BooleanVar(value=False)
        self.study_switch = ctk.CTkSwitch(
            input_card, text="Study-only (hints, no answers)", variable=self.study_var,
            command=self._on_study_toggle, progress_color=T.ACCENT, button_color=T.TEXT,
            fg_color=T.BORDER, text_color=T.TEXT_MUTED, font=T.font(12))
        self.analyze_text_btn = ctk.CTkButton(input_card, text="✉  Analyze Pasted Text",
                                              command=self._analyze_text, **T.secondary_button())

        # capture region
        region_card = self._card(left)
        region_card.grid(row=row, column=0, sticky="ew", pady=4, padx=2); row += 1
        region_card.grid_columnconfigure((0, 1), weight=1)
        self.region_label = ctk.CTkLabel(region_card, text="Capture area: full screen",
                                         font=T.font(12), text_color=T.TEXT_MUTED, anchor="w")
        self.region_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 6))
        ctk.CTkButton(region_card, text="⬚  Select Region", command=self._select_region,
                      **T.secondary_button()).grid(row=1, column=0, sticky="ew", padx=(12, 4),
                                                   pady=(0, 12))
        ctk.CTkButton(region_card, text="Full Screen", command=self._clear_region,
                      **T.secondary_button()).grid(row=1, column=1, sticky="ew", padx=(4, 12),
                                                   pady=(0, 12))

        ctk.CTkLabel(left, text="Screenshots go to Google Gemini only when a task runs.\n"
                                "They are kept in memory only and never saved to disk.",
                     font=T.font(10), text_color=T.TEXT_DIM, justify="left", anchor="w"
                     ).grid(row=row, column=0, sticky="ew", padx=6, pady=(6, 10))

    def _build_right(self) -> None:
        right = ctk.CTkFrame(self, fg_color=T.BG)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, T.PAD), pady=6)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=3)
        right.grid_rowconfigure(1, weight=1, minsize=170)

        results = self._card(right)
        results.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        results.grid_columnconfigure(0, weight=1)
        results.grid_rowconfigure(2, weight=1)
        head = ctk.CTkFrame(results, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        head.grid_columnconfigure(1, weight=1)
        self._caption(head, "RESULTS").grid(row=0, column=0, sticky="w")
        self.source_badge = ctk.CTkLabel(head, text="", font=T.font(10, "bold"), height=22,
                                         corner_radius=6, fg_color=T.SURFACE, text_color=T.TEXT_DIM)
        self.source_badge.grid(row=0, column=1, sticky="w", padx=10)
        self.copy_btn = ctk.CTkButton(head, text="⧉  Copy Result", width=120,
                                      command=self._copy_result, **T.primary_button(height=30))
        self.copy_btn.grid(row=0, column=2, sticky="e", padx=(6, 0))
        self.copy_all_btn = ctk.CTkButton(head, text="Copy All", width=80,
                                          command=self._copy_all, **T.secondary_button(height=30))
        self.copy_all_btn.grid(row=0, column=3, sticky="e", padx=(6, 0))

        self.error_banner = ctk.CTkFrame(results, fg_color="#2A1414", corner_radius=T.RADIUS_SM,
                                         border_width=1, border_color=T.ERROR)
        self.error_banner.grid_columnconfigure(0, weight=1)
        self.error_text = ctk.CTkLabel(self.error_banner, text="", font=T.font(12),
                                       text_color="#FECACA", justify="left", anchor="w",
                                       wraplength=700)
        self.error_text.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        ctk.CTkButton(self.error_banner, text="↻ Retry", width=80, command=self._retry,
                      **T.secondary_button(height=28)).grid(row=0, column=1, padx=4)
        ctk.CTkButton(self.error_banner, text="Dismiss", width=70, command=self._hide_error_banner,
                      **T.secondary_button(height=28)).grid(row=0, column=2, padx=(0, 10))

        self.results_body = ctk.CTkScrollableFrame(results, fg_color=T.CARD,
                                                   scrollbar_button_color=T.SURFACE,
                                                   scrollbar_button_hover_color=T.BORDER)
        self.results_body.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 10))
        self.results_body.grid_columnconfigure(0, weight=1)
        self.results_body.bind("<Configure>", lambda _e: self._update_wraps(), add="+")

        log = self._card(right)
        log.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        log.grid_columnconfigure(0, weight=1)
        log.grid_rowconfigure(1, weight=1)
        self._caption(log, "ACTIVITY LOG").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 2))
        self.log_box = ctk.CTkTextbox(log, fg_color=T.BG, text_color=T.TEXT_MUTED, font=T.mono(11),
                                      border_width=0, wrap="word", height=120)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        for level, color in T.LOG_LEVEL_COLORS.items():
            self.log_box.tag_config(level, foreground=color)
        self.log_box.tag_config("time", foreground=T.TEXT_DIM)
        self.log_box.configure(state="disabled")

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=T.CARD, corner_radius=0, height=30,
                              border_width=0)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.footer_labels = {}
        for key in ("gemini", "mode", "monitor", "requests"):
            label = ctk.CTkLabel(footer, text="", font=T.font(11), text_color=T.TEXT_MUTED)
            label.pack(side="left", padx=(T.PAD, 8), pady=4)
            self.footer_labels[key] = label
        ctk.CTkLabel(footer, text="Practice & permitted tasks only — nothing is ever submitted "
                                  "for you", font=T.font(10), text_color=T.TEXT_DIM
                     ).pack(side="right", padx=T.PAD)
        self._update_footer()

    # ================================================================== helpers
    def _on_configure(self, event) -> None:
        if event.widget is not self:
            return
        if self.state() == "iconic":
            self.screens.set_own_window(None)
        else:
            self.screens.set_own_window((self.winfo_rootx(), self.winfo_rooty(),
                                         self.winfo_width(), self.winfo_height()))

    def _wrap_width(self) -> int:
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        return max(int(self.results_body.winfo_width() / scaling) - 70, 300)

    def _update_wraps(self) -> None:
        width = self._wrap_width()
        alive = []
        for label in self._wrap_labels:
            if label.winfo_exists():
                label.configure(wraplength=width)
                alive.append(label)
        self._wrap_labels = alive
        self.error_text.configure(wraplength=width - 150)

    def _set_button(self, button: ctk.CTkButton, enabled: bool, text: str | None = None) -> None:
        kwargs = {"state": "normal" if enabled else "disabled"}
        if text is not None:
            kwargs["text"] = text
        button.configure(**kwargs)

    def _update_footer(self) -> None:
        if self.service.is_mock:
            gem, color = "Gemini: MOCK MODE (no real AI)", T.WARNING
        elif not self._gemini_ok:
            gem, color = "Gemini: not configured", T.ERROR
        else:
            gem, color = f"Gemini: {getattr(self, '_gemini_status', 'checking…')}", T.ACCENT
        self.footer_labels["gemini"].configure(text=f"● {gem}", text_color=color)
        self.footer_labels["mode"].configure(text=f"Mode: {self.controller.mode.title}")
        monitoring = self.controller.monitoring
        region = self.screens.region
        area = region.describe() if region else "full screen"
        self.footer_labels["monitor"].configure(
            text=f"Monitoring: {'ON' if monitoring else 'off'} ({area})",
            text_color=T.ACCENT if monitoring else T.TEXT_MUTED)
        self.footer_labels["requests"].configure(
            text=f"API requests this session: {self.service.request_count} / "
                 f"{self.service.settings.session_request_budget}")

    def _verify_gemini(self) -> None:
        try:
            name = self.service.verify()
            self.events.put(AgentEvent("verify", data=(True, f"connected · {name}")))
        except AgentError as err:
            self.events.put(AgentEvent("verify", data=(False, err)))

    # ================================================================== events
    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            for _ in range(200):
                event: AgentEvent = self.events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        except Exception:
            self.logger._file_logger.exception("UI event handling failed")
        self.after(80, self._poll_events)

    def _handle_event(self, event: AgentEvent) -> None:
        kind = event.kind
        if kind == "log":
            self._append_log(event.data)
        elif kind == "state":
            self._apply_state(event.data)
        elif kind == "task":
            self._current_task = event.task_id
            self._hide_error_banner()
            self._refresh_task_label()
        elif kind == "result":
            self._render_result(event.data, event.extra)
            self._refresh_task_label()
        elif kind == "error":
            self._show_error_banner(event.data)
        elif kind == "counter":
            self._update_footer()
        elif kind == "preview":
            self._open_preview(event.data)
        elif kind == "fill_done":
            self._on_fill_done(event.data)
        elif kind == "fill_progress":
            self.op_detail.configure(text=event.data)
        elif kind == "verify":
            ok, info = event.data
            if ok:
                self._gemini_status = info
                self.logger.ok(f"Gemini {info}.")
            else:
                self._gemini_status = f"error ({info.category.value})"
                if info.category in (ErrorCategory.AUTH, ErrorCategory.CONFIG):
                    self._gemini_ok = False
                self.logger.error(f"Gemini check failed — {info.message}")
                self._show_error_banner(info)
            self._update_footer()
            self._refresh_controls()

    def _append_log(self, entry: LogEntry) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{entry.timestamp:%H:%M:%S}  ", "time")
        self.log_box.insert("end", f"{entry.message}\n", entry.level)
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 400:
            self.log_box.delete("1.0", f"{lines - 400}.0")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def _apply_state(self, state: AgentState) -> None:
        color = T.STATUS_COLORS[state.value]
        self.status_pill.configure(text=f"●  {T.STATUS_LABELS[state.value]}", text_color=color)
        op, detail = STATE_TEXT[state]
        if state == AgentState.RUNNING:
            detail = (f"Sampling every {self.controller.settings.monitor_interval_s:g}s locally; "
                      "only meaningful changes are sent to Gemini.")
        self.op_label.configure(text=op, text_color=color if state == AgentState.ERROR else T.TEXT)
        self.op_detail.configure(text=detail)
        if state == AgentState.PROCESSING:
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(0)
        self._refresh_controls()
        self._update_footer()

    def _refresh_task_label(self) -> None:
        task = f"#{self._current_task}" if self._current_task else "—"
        self.task_label.configure(text=f"Task: {task}   ·   Last success: "
                                       f"{self.controller.last_success}")

    def _refresh_controls(self) -> None:
        state = self.controller.state
        monitoring = self.controller.monitoring
        busy = self.controller.busy or state == AgentState.PROCESSING or self._filling
        ready = self._gemini_ok
        self._set_button(self.start_btn, ready and not monitoring and not busy)
        if monitoring and state in (AgentState.PAUSED, AgentState.WAITING_FOR_REVIEW):
            self._set_button(self.pause_btn, not self._filling, "▶  Resume")
        else:
            self._set_button(self.pause_btn, monitoring and state in (AgentState.RUNNING,
                                                                      AgentState.PROCESSING),
                             "⏸  Pause")
        self._set_button(self.stop_btn, monitoring or busy)
        one_shot_ok = ready and not busy and (not monitoring or state == AgentState.PAUSED)
        self._set_button(self.once_btn, one_shot_ok)
        self._set_button(self.analyze_text_btn, one_shot_ok)
        self._set_button(self.retry_btn, one_shot_ok and self.controller.can_retry)
        self._set_button(self.clear_btn, not busy)
        self._set_button(self.copy_btn, self._result is not None)
        self._set_button(self.copy_all_btn, self._result is not None)
        locked = monitoring or busy
        for key, parts in self.mode_cards.items():
            parts["card"].configure(cursor="arrow" if locked else "hand2")

    # ================================================================== mode & input
    def _select_mode(self, key: str, initial: bool = False) -> None:
        if not initial:
            if key == self.controller.mode.key:
                return
            self._mode_inputs[self.controller.mode.key] = self.input_box.get("1.0", "end-1c")
            if not self.controller.set_mode(key):
                return
            self._clear_results_view()
        for k, parts in self.mode_cards.items():
            selected = k == key
            parts["card"].configure(border_color=T.ACCENT if selected else T.BORDER,
                                    fg_color=T.SURFACE if selected else T.CARD,
                                    border_width=2 if selected else 1)
            parts["icon"].configure(fg_color=T.ACCENT if selected else T.SURFACE,
                                    text_color=T.ACCENT_TEXT if selected else T.ACCENT)
        spec = MODES[key]
        self.input_label.configure(text=spec.input_label)
        self.input_hint.configure(text=spec.input_placeholder)
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", self._mode_inputs[key])
        self.study_switch.grid_forget()
        self.analyze_text_btn.grid_forget()
        if key == "practice":
            self.study_switch.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 12))
        elif spec.supports_text_input:
            self.analyze_text_btn.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._sync_context()
        self._update_footer()
        self._refresh_controls()

    def _sync_context(self) -> None:
        text = self.input_box.get("1.0", "end-1c")
        self._mode_inputs[self.controller.mode.key] = text
        study = self.study_var.get() and self.controller.mode.key == "practice"
        # In feedback mode the box holds text to analyze, not context for screenshots.
        ctx_text = "" if self.controller.mode.supports_text_input else text
        self.controller.set_context(ModeContext(ctx_text, study))

    def _on_study_toggle(self) -> None:
        self._sync_context()
        if self.study_var.get():
            self.logger.info("Study-only mode ON — answers hidden, answer entry disabled.")
        else:
            self.logger.info("Study-only mode OFF — use only where AI help is permitted.")

    # ================================================================== commands
    def _start(self) -> None:
        self._sync_context()
        if self.controller.mode.key == "feedback" and self.input_box.get("1.0", "end-1c").strip():
            self.logger.info("Continuous mode reads the screen; use Analyze Pasted Text for "
                             "the pasted text.")
        if self.controller.start():
            self._update_footer()
        self._refresh_controls()

    def _pause_resume(self) -> None:
        if self.controller.state in (AgentState.PAUSED, AgentState.WAITING_FOR_REVIEW):
            self.controller.resume()
        else:
            self.controller.pause()
        self._refresh_controls()

    def _stop(self) -> None:
        if self._filling:
            self.automation.cancel.set()
            self.logger.warn("Stop requested — automation will halt before the next keystroke.")
        self.controller.stop()
        self._refresh_controls()
        self._update_footer()

    def _capture_once(self) -> None:
        self._sync_context()
        self.controller.capture_once()
        self._refresh_controls()

    def _analyze_text(self) -> None:
        self._sync_context()
        self.controller.analyze_text(self.input_box.get("1.0", "end-1c"))
        self._refresh_controls()

    def _retry(self) -> None:
        self._hide_error_banner()
        self.controller.retry()
        self._refresh_controls()

    def _clear(self) -> None:
        self.controller.clear()
        self._clear_results_view()
        self.logger.info("Results cleared (last screenshot discarded from memory).")
        self._refresh_controls()

    def _clear_results_view(self) -> None:
        self._result = None
        self._result_meta = {}
        self._hide_error_banner()
        self._render_empty()

    # ---------------------------------------------------------------- copy
    def _copy(self, text: str, what: str) -> None:
        if not text.strip():
            self.logger.warn(f"Nothing to copy for {what}.")
            return
        try:
            copy_to_clipboard(text)
            self.logger.ok(f"Copied {what} to clipboard.")
        except AgentError as err:
            self.logger.error(err.message)
            self._show_error_banner(err)

    def _current_form_values(self) -> str:
        return "\n".join(f"{field.label}: {value.get().strip()}"
                         for field, _ok, value, *_ in self._form_rows if value.get().strip())

    def _copy_result(self) -> None:
        if self._result is None:
            return
        if isinstance(self._result, FormResult):
            self._copy(self._current_form_values(), "field values")
        elif isinstance(self._result, PracticeResult) and self._result_meta.get("study_only"):
            self._copy(self._result.explanation, "hint")
        else:
            self._copy(MODES[self._result_meta["mode"]].copy_text(self._result), "result")

    def _copy_all(self) -> None:
        result = self._result
        if isinstance(result, PracticeResult):
            text = practice_mode.full_text(result)
        elif isinstance(result, FormResult):
            text = self._current_form_values()
        elif isinstance(result, FeedbackResult):
            text = (f"Overall: {result.overall_feedback}\n\nImproved version:\n"
                    f"{result.corrected_version}\n\nNotes:\n" +
                    "\n".join(f"- {n}" for n in result.revision_notes))
        else:
            return
        self._copy(text, "full result")

    # ================================================================== results rendering
    def _clear_body(self) -> None:
        for child in self.results_body.winfo_children():
            child.destroy()
        self._wrap_labels = []
        self._form_rows = []

    def _wrap_label(self, master, text: str, size: int = 13, color: str = T.TEXT,
                    weight: str = "normal", **grid) -> ctk.CTkLabel:
        label = ctk.CTkLabel(master, text=text, font=T.font(size, weight), text_color=color,
                             justify="left", anchor="w", wraplength=self._wrap_width())
        self._wrap_labels.append(label)
        if grid:
            label.grid(**grid)
        return label

    def _section(self, title: str, body: str = "", accent: bool = False, color: str = T.TEXT,
                 copy: str | None = None, size: int = 13, border: str | None = None):
        row = len(self.results_body.winfo_children())
        frame = ctk.CTkFrame(self.results_body, fg_color=T.SURFACE, corner_radius=T.RADIUS_SM,
                             border_width=1, border_color=border or (T.ACCENT if accent else T.BORDER))
        frame.grid(row=row, column=0, sticky="ew", padx=4, pady=5)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title.upper(), font=T.font(10, "bold"),
                     text_color=T.ACCENT if accent else T.TEXT_DIM, anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
        if copy is not None:
            ctk.CTkButton(frame, text="⧉ Copy", width=64,
                          command=lambda: self._copy(copy, title.lower()),
                          **T.secondary_button(height=24, font=T.font(11))
                          ).grid(row=0, column=1, sticky="e", padx=8, pady=(6, 0))
        if body:
            self._wrap_label(frame, body, size=size, color=color, row=1, column=0, columnspan=2,
                             sticky="ew", padx=12, pady=(2, 10))
        return frame

    def _render_empty(self) -> None:
        self._clear_body()
        self.source_badge.configure(text="")
        spec = self.controller.mode
        steps = {
            "practice": "Open a practice question, then click ◎ Capture Once.\n"
                        "You'll get the detected question, a suggested answer and an explanation.",
            "form": "Type your details on the left, open the form, then ◎ Capture Once.\n"
                    "Review every suggested value before anything is typed. Nothing is submitted.",
            "feedback": "Paste text on the left and click Analyze Pasted Text — or capture text "
                        "on screen.\nYou'll get specific feedback and an improved version.",
        }[spec.key]
        frame = ctk.CTkFrame(self.results_body, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", pady=60)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=spec.icon, font=T.font(40), text_color=T.BORDER
                     ).grid(row=0, column=0)
        ctk.CTkLabel(frame, text=spec.title, font=T.font(16, "bold"), text_color=T.TEXT_MUTED
                     ).grid(row=1, column=0, pady=(4, 6))
        ctk.CTkLabel(frame, text=steps, font=T.font(12), text_color=T.TEXT_DIM, justify="center"
                     ).grid(row=2, column=0)
        self._refresh_controls()

    def _render_result(self, result, meta: dict) -> None:
        self._result, self._result_meta = result, meta
        self._clear_body()
        if meta.get("mock"):
            self.source_badge.configure(text="  MOCK RESULT — NOT REAL AI  ", fg_color=T.WARNING,
                                        text_color="#2A1A00")
        else:
            self.source_badge.configure(text=f"  AI SUGGESTION · {self.service.model}  ",
                                        fg_color=T.SURFACE, text_color=T.ACCENT)
        if isinstance(result, PracticeResult):
            self._render_practice(result, meta.get("study_only", False))
        elif isinstance(result, FormResult):
            self._render_form(result)
        elif isinstance(result, FeedbackResult):
            self._render_feedback(result)
        self.results_body._parent_canvas.yview_moveto(0)
        self._refresh_controls()

    def _render_practice(self, r: PracticeResult, study_only: bool) -> None:
        if r.graded_assessment_suspected:
            self._section("⚠ Possible graded assessment",
                          "This screen looks like a live graded or proctored test. CHEATER.exe "
                          "is for practice — follow your assessment's rules. Answer entry is "
                          "disabled.", color=T.WARNING, border=T.WARNING)
        if r.task_type == "no_question_found":
            self._section("No question found", r.explanation or r.uncertainty_notes,
                          color=T.WARNING, border=T.WARNING)
            return
        question = r.detected_question
        if r.options:
            question += "\n\n" + "\n".join(r.options)
        self._section(f"Detected question · {r.task_type.replace('_', ' ')}", question,
                      copy=question)
        if study_only:
            self._section("Study-only mode", "The answer is hidden. Use the hint below to work "
                                             "it out yourself.", color=T.INFO)
            self._section("Concept & hint", r.explanation, accent=True, copy=r.explanation)
        else:
            conf_color = {"high": T.ACCENT, "medium": T.WARNING, "low": T.ERROR}[r.confidence]
            frame = self._section("Suggested answer", r.suggested_answer, accent=True, size=16,
                                  copy=r.suggested_answer)
            info = ctk.CTkFrame(frame, fg_color="transparent")
            info.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))
            ctk.CTkLabel(info, text=f" {r.confidence.upper()} CONFIDENCE ", corner_radius=6,
                         fg_color=T.BG, text_color=conf_color, font=T.font(10, "bold"),
                         height=22).pack(side="left")
            ctk.CTkLabel(info, text="  Model-generated suggestion — not verified. Check it.",
                         font=T.font(11), text_color=T.TEXT_DIM).pack(side="left")
            allowed, reason = practice_mode.answer_entry_allowed(r, study_only)
            if allowed:
                ctk.CTkButton(info, text="⌨ Type into focused field", width=170,
                              command=lambda: self._confirm_and_fill(
                                  [FillStep("Answer", r.suggested_answer, True)],
                                  "Type the suggested answer into the field you focus?"),
                              **T.secondary_button(height=26, font=T.font(11))).pack(side="right")
            self._section("Explanation", r.explanation, copy=r.explanation)
        if r.uncertainty_notes:
            self._section("Uncertainty", r.uncertainty_notes, color=T.WARNING)

    def _render_form(self, r: FormResult) -> None:
        if r.form_title or r.notes:
            self._section(r.form_title or "Form", r.notes, color=T.TEXT_MUTED)
        if r.missing_information:
            self._section("Information needed from you",
                          "\n".join(f"• {m}" for m in r.missing_information) +
                          "\n\nAdd these to “Your details” and capture again, or type values "
                          "below.", color=T.WARNING, border=T.WARNING)
        if not r.fields:
            self._section("No supported fields detected", "Try selecting a region around the "
                          "form.", color=T.WARNING)
            return
        table = self._section(f"Detected fields ({len(r.fields)}) — tick the ones to fill")
        table.grid_columnconfigure(0, weight=1)
        for i, field in enumerate(r.fields):
            row = ctk.CTkFrame(table, fg_color=T.CARD, corner_radius=T.RADIUS_SM)
            row.grid(row=i + 1, column=0, columnspan=2, sticky="ew", padx=8, pady=3)
            row.grid_columnconfigure(2, weight=1)
            approved = tk.BooleanVar(value=default_approval(field))
            value = tk.StringVar(value=field.suggested_value)
            fillable_type = not is_sensitive(field) and not field.read_only and \
                field.field_type in {"text", "email", "phone", "date", "number", "textarea"}
            check = ctk.CTkCheckBox(row, text="", variable=approved, width=24,
                                    fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                    checkmark_color=T.ACCENT_TEXT, border_color=T.BORDER,
                                    state="normal" if fillable_type else "disabled")
            check.grid(row=0, column=0, rowspan=2, padx=(10, 4))
            name = field.label + (" *" if field.required else "")
            ctk.CTkLabel(row, text=name, font=T.font(12, "bold"), text_color=T.TEXT, anchor="w",
                         width=150).grid(row=0, column=1, sticky="w", padx=4, pady=(6, 0))
            entry = ctk.CTkEntry(row, textvariable=value, fg_color=T.SURFACE, border_color=T.BORDER,
                                 text_color=T.TEXT, font=T.font(12), height=30,
                                 placeholder_text="(needs your input)" if not is_sensitive(field)
                                 else "never filled")
            entry.grid(row=0, column=2, sticky="ew", padx=4, pady=(6, 0))
            if is_sensitive(field) or field.read_only:
                entry.configure(state="disabled")
            ctk.CTkButton(row, text="⧉", width=30, command=lambda v=value, f=field:
                          self._copy(v.get(), f.label), **T.secondary_button(height=28)
                          ).grid(row=0, column=3, padx=2, pady=(6, 0))
            ctk.CTkButton(row, text="⌨", width=30,
                          command=lambda v=value, f=field: self._fill_single(f, v.get()),
                          state="normal" if fillable_type else "disabled",
                          **T.secondary_button(height=28)
                          ).grid(row=0, column=4, padx=(2, 10), pady=(6, 0))
            meta = (f"{field.field_type} · source: {field.source_of_value.replace('_', ' ')} · "
                    f"confidence {field.confidence:.0%}")
            if field.notes:
                meta += f" · {field.notes}"
            meta_color = T.WARNING if (field.requires_confirmation or field.confidence < 0.75) \
                else T.TEXT_DIM
            ctk.CTkLabel(row, text=meta, font=T.font(10), text_color=meta_color, anchor="w",
                         justify="left").grid(row=1, column=1, columnspan=4, sticky="w",
                                              padx=4, pady=(0, 6))
            self._form_rows.append((field, approved, value))
        actions = ctk.CTkFrame(table, fg_color="transparent")
        actions.grid(row=len(r.fields) + 1, column=0, columnspan=2, sticky="ew", padx=8,
                     pady=(6, 10))
        ctk.CTkButton(actions, text="⌨  Fill ticked fields (Tab order)", width=230,
                      command=self._fill_sequence, **T.primary_button(height=34)
                      ).pack(side="left")
        ctk.CTkLabel(actions, text="  You focus the first ticked field; the form is never "
                                   "submitted.", font=T.font(11), text_color=T.TEXT_DIM
                     ).pack(side="left")

    def _render_feedback(self, r: FeedbackResult) -> None:
        if not r.text_found:
            self._section("No readable text", r.overall_feedback + "\nPaste the text instead, or "
                          "select a clearer region.", color=T.WARNING, border=T.WARNING)
            return
        self._section("Overall assessment", r.overall_feedback)
        if r.strengths:
            self._section("Strengths", "\n".join(f"✓ {s}" for s in r.strengths), color=T.ACCENT)
        if r.improvements:
            text = "\n\n".join(f"[{i.category.replace('_', ' ').upper()}]  {i.issue}\n→ "
                               f"{i.suggestion}" for i in r.improvements)
            self._section(f"Improvements ({len(r.improvements)})", text)
        self._section("Original text", r.original_text, color=T.TEXT_MUTED)
        self._section("Improved version", r.corrected_version, accent=True,
                      copy=r.corrected_version)
        if r.revision_notes:
            self._section("Revision notes", "\n".join(f"• {n}" for n in r.revision_notes))
        if r.uncertainty_notes:
            self._section("Uncertainty", r.uncertainty_notes, color=T.WARNING)

    def _show_error_banner(self, err: AgentError) -> None:
        text = err.user_text()
        self.error_text.configure(text=text)
        self.error_banner.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

    def _hide_error_banner(self) -> None:
        self.error_banner.grid_forget()

    # ================================================================== form filling
    def _fill_single(self, field, value: str) -> None:
        if not can_fill(field.model_copy(update={"suggested_value": value})):
            self.logger.warn(f"“{field.label}” can't be filled automatically — copy it instead.")
            return
        self._confirm_and_fill([FillStep(field.label, value.strip(), True)],
                               f"Type the value for “{field.label}” into the field you focus?")

    def _fill_sequence(self) -> None:
        fields = [row[0] for row in self._form_rows]
        approved = [row[1].get() for row in self._form_rows]
        values = [row[2].get() for row in self._form_rows]
        steps, note = plan_sequential_fill(fields, approved, values)
        if note:
            self.logger.info(note)
        if not any(s.fill for s in steps):
            self.logger.warn("No ticked fields with values — nothing to fill.")
            return
        plan = "\n".join(f"  {'✎' if s.fill else '↷'}  {s.label}" for s in steps)
        self._confirm_and_fill(steps, "Fill these fields in Tab order (↷ = skipped)?\n\n" + plan +
                               (f"\n\n{note}" if note else ""))

    def _confirm_and_fill(self, steps: list[FillStep], question: str) -> None:
        if self._filling or self.controller.monitoring and \
                self.controller.state == AgentState.RUNNING:
            self.logger.warn("Pause the agent before filling fields.")
            return
        ok = messagebox.askokcancel(
            "Confirm entry — CHEATER.exe",
            f"{question}\n\nAfter OK you have {COUNTDOWN_S} seconds to CLICK INTO the first target "
            "field. Values are pasted via the clipboard and Tab moves to the next field.\n\n"
            "Nothing will be submitted. Press Stop, or move the mouse into a screen corner, to "
            "abort.", parent=self)
        if not ok:
            self.logger.info("Fill cancelled by user.")
            return
        self._filling = True
        self._refresh_controls()
        self._countdown(COUNTDOWN_S, steps)

    def _countdown(self, remaining: int, steps: list[FillStep]) -> None:
        if self.automation.cancel.is_set():
            self.automation.cancel.clear()
            self._filling = False
            self.logger.warn("Fill aborted before typing started.")
            self._refresh_controls()
            return
        if remaining > 0:
            self.op_label.configure(text=f"Click into the target field… {remaining}")
            self.op_detail.configure(text="Typing starts when the countdown ends.")
            self.after(1000, self._countdown, remaining - 1, steps)
            return
        self.op_label.configure(text="Entering values…")

        def work():
            outcomes = self.automation.run_fill(
                steps, progress=lambda m: self.events.put(AgentEvent("fill_progress", data=m)))
            self.events.put(AgentEvent("fill_done", data=outcomes))

        threading.Thread(target=work, name="fill", daemon=True).start()

    def _on_fill_done(self, outcomes) -> None:
        self._filling = False
        entered = sum(1 for o in outcomes if o.status.startswith("entered"))
        problems = [o for o in outcomes if not o.status.startswith(("entered", "skipped"))]
        level = self.logger.warn if problems else self.logger.ok
        level(f"Fill finished: {entered} entered, {len(problems)} not completed. "
              "Verify the form on screen — nothing was submitted.")
        report = "\n".join(f"{'✓' if o.status.startswith('entered') else '•'} {o.label}: {o.status}"
                           for o in outcomes)
        self._section("Fill report", report, color=T.WARNING if problems else T.ACCENT)
        self._apply_state(self.controller.state)

    # ================================================================== region / preview
    def _select_region(self) -> None:
        if self.controller.monitoring and self.controller.state == AgentState.RUNNING:
            self.logger.warn("Pause the agent before changing the capture region.")
            return
        self.withdraw()
        self.after(250, lambda: RegionSelector(self, self._on_region))

    def _on_region(self, region: Region | None) -> None:
        self.deiconify()
        if region is None:
            self.logger.info("Region selection cancelled.")
            return
        self.screens.set_region(region)
        self.controller.detector.reset()
        self.region_label.configure(text=f"Capture area: {region.describe()}", text_color=T.ACCENT)
        self.logger.ok(f"Capture region set to {region.describe()}.")
        self._update_footer()

    def _clear_region(self) -> None:
        self.screens.set_region(None)
        self.controller.detector.reset()
        self.region_label.configure(text="Capture area: full screen", text_color=T.TEXT_MUTED)
        self.logger.info("Capture area set to full screen.")
        self._update_footer()

    def _preview(self) -> None:
        if self.controller.last_capture is not None:
            self._open_preview(self.controller.last_capture)
            return

        def grab():
            try:
                image = self.screens.capture().image
                self.events.put(AgentEvent("preview", data=image))
            except AgentError as err:
                self.events.put(AgentEvent("error", data=err))

        self.logger.info("Taking a local preview capture (not sent anywhere).")
        threading.Thread(target=grab, daemon=True).start()

    def _open_preview(self, image: Image.Image) -> None:
        window = ctk.CTkToplevel(self, fg_color=T.BG)
        window.title("Screenshot preview — CHEATER.exe")
        window.transient(self)
        preview = image.copy()
        preview.thumbnail((960, 600))
        photo = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
        ctk.CTkLabel(window, text="", image=photo).pack(padx=16, pady=(16, 8))
        window._photo = photo  # keep a reference
        ctk.CTkLabel(window, text=f"{image.width}×{image.height}px · this is what gets sent "
                                  "(CHEATER.exe window blacked out) · held in memory only",
                     font=T.font(11), text_color=T.TEXT_MUTED).pack(pady=(0, 14))
        window.after(150, window.focus_force)

    # ================================================================== settings
    def _open_settings(self) -> None:
        SettingsDialog(self, self.controller.settings, self._apply_settings,
                       self.service.model, self.service.is_mock)

    def _apply_settings(self, settings: AgentSettings) -> None:
        self.controller.apply_settings(settings)
        try:
            save_settings(settings)
            self.logger.ok("Settings saved.")
        except OSError:
            self.logger.warn("Settings applied for this session but could not be saved.")

    # ================================================================== shutdown
    def _on_close(self) -> None:
        self._closing = True
        self.automation.cancel.set()
        self.controller.shutdown()
        self.destroy()


class RegionSelector(tk.Toplevel):
    """Full-screen translucent overlay: drag a rectangle, Esc to cancel."""

    def __init__(self, master, callback):
        super().__init__(master)
        self._callback = callback
        self._start = None
        self._rect = None
        self.overrideredirect(True)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.30)
        self.configure(bg="black", cursor="crosshair")
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(self.winfo_screenwidth() // 2, 60, fill="white",
                                font=(T.FONT_FAMILY, 18, "bold"),
                                text="Drag to select the capture region  ·  Esc to cancel")
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda _e: self._finish(None))
        self.after(50, self.focus_force)

    def _press(self, event):
        self._start = (event.x_root, event.y_root)
        self._rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                  outline=T.ACCENT, width=3)

    def _drag(self, event):
        if self._rect is not None:
            x0, y0 = self._start[0] - self.winfo_rootx(), self._start[1] - self.winfo_rooty()
            self.canvas.coords(self._rect, x0, y0, event.x, event.y)

    def _release(self, event):
        if self._start is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x_root, event.y_root
        left, top = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        self._finish(Region(left, top, width, height) if width >= 40 and height >= 40 else None)

    def _finish(self, region):
        self.destroy()
        self._callback(region)


class SettingsDialog(ctk.CTkToplevel):
    FIELDS = [
        ("monitor_interval_s", "Monitoring interval (seconds)", float),
        ("change_threshold", "Change sensitivity (fraction of screen, e.g. 0.004)", float),
        ("settle_time_s", "Settle time before sending (seconds)", float),
        ("max_image_side", "Max upload image side (px)", int),
        ("request_timeout_s", "Request timeout (seconds)", float),
        ("max_retries", "Auto-retries for timeouts (each costs quota)", int),
        ("min_request_gap_s", "Min seconds between requests (continuous)", float),
        ("session_request_budget", "Max API requests per session", int),
    ]

    def __init__(self, master, settings: AgentSettings, on_save, model: str, mock: bool):
        super().__init__(master, fg_color=T.BG)
        self.title("Settings — CHEATER.exe")
        self.transient(master)
        self.resizable(False, False)
        self._on_save = on_save
        self._vars = {}
        ctk.CTkLabel(self, text="Agent settings", font=T.font(16, "bold"), text_color=T.TEXT
                     ).grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(self, text=f"Model: {model}{'  (mock mode)' if mock else ''} — change "
                                "GEMINI_MODEL in .env", font=T.font(11), text_color=T.TEXT_MUTED
                     ).grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 10))
        for i, (name, label, _cast) in enumerate(self.FIELDS, start=2):
            ctk.CTkLabel(self, text=label, font=T.font(12), text_color=T.TEXT, anchor="w"
                         ).grid(row=i, column=0, sticky="w", padx=18, pady=4)
            var = tk.StringVar(value=str(getattr(settings, name)))
            ctk.CTkEntry(self, textvariable=var, width=110, fg_color=T.SURFACE,
                         border_color=T.BORDER, text_color=T.TEXT
                         ).grid(row=i, column=1, padx=18, pady=4)
            self._vars[name] = var
        self.error = ctk.CTkLabel(self, text="", text_color=T.ERROR, font=T.font(11))
        self.error.grid(row=20, column=0, columnspan=2, sticky="w", padx=18)
        ctk.CTkButton(self, text="Save", command=self._save, **T.primary_button()
                      ).grid(row=21, column=1, sticky="e", padx=18, pady=(6, 16))
        self.after(150, self.focus_force)

    def _save(self):
        try:
            values = {name: cast(self._vars[name].get()) for name, _l, cast in self.FIELDS}
        except ValueError:
            self.error.configure(text="Please enter valid numbers.")
            return
        self._on_save(AgentSettings(**values).clamp())
        self.destroy()

"""The One-Click Agent engine shared by all modes.

Owns the state machine, background workers, change detection and request de-duplication.
It never touches widgets: everything the UI needs arrives as AgentEvent objects on a
thread-safe queue that the UI drains on its own thread.
"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PIL import Image

from app.activity_logger import ActivityLogger
from app.config import AgentSettings
from app.error_handler import AgentError, ErrorCategory, classify_exception
from app.gemini_service import GeminiService
from app.modes import MODES, ModeContext, ModeSpec
from app.screen_change_detector import ChangeStatus, ScreenChangeDetector
from app.screenshot_service import prepare_for_upload


class AgentState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    PROCESSING = "PROCESSING"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


S = AgentState
TRANSITIONS: dict[AgentState, set[AgentState]] = {
    S.IDLE: {S.RUNNING, S.PROCESSING, S.STOPPED},
    S.RUNNING: {S.PROCESSING, S.PAUSED, S.STOPPED, S.ERROR},
    S.PROCESSING: {S.RUNNING, S.PAUSED, S.WAITING_FOR_REVIEW, S.ERROR, S.STOPPED, S.IDLE},
    S.PAUSED: {S.RUNNING, S.PROCESSING, S.STOPPED, S.IDLE},
    S.WAITING_FOR_REVIEW: {S.IDLE, S.RUNNING, S.PROCESSING, S.STOPPED, S.PAUSED},
    S.ERROR: {S.IDLE, S.RUNNING, S.PROCESSING, S.STOPPED},
    S.STOPPED: {S.IDLE, S.RUNNING, S.PROCESSING},
}

# Errors that make continuous monitoring pointless until the user intervenes.
_PAUSE_CATEGORIES = {ErrorCategory.RATE_LIMIT, ErrorCategory.AUTH, ErrorCategory.CONFIG}


@dataclass
class AgentEvent:
    kind: str                      # state | task | result | error | capture | log
    task_id: int | None = None
    data: Any = None
    extra: dict = field(default_factory=dict)


@dataclass
class _Run:
    """Per-monitoring-run signals, so a stopped run can never be revived by a new one."""
    generation: int
    stop: threading.Event = field(default_factory=threading.Event)
    resume: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


class AgentController:
    def __init__(self, service: GeminiService, screenshots, logger: ActivityLogger,
                 settings: AgentSettings, events: queue.Queue | None = None,
                 detector: ScreenChangeDetector | None = None):
        self.service = service
        self.screenshots = screenshots
        self.logger = logger
        self.settings = settings
        self.events: queue.Queue = events if events is not None else queue.Queue()
        self.detector = detector or ScreenChangeDetector(settings.change_threshold,
                                                         settings.settle_time_s)
        self.mode: ModeSpec = MODES["practice"]
        self.context = ModeContext()
        self._lock = threading.RLock()
        self._request_lock = threading.Lock()   # one in-flight Gemini request per pipeline
        self._state = AgentState.IDLE
        self._generation = 0
        self._task_seq = 0
        self._run: _Run | None = None
        self._last_payload: tuple[bytes | None, ModeContext, ModeSpec] | None = None
        self.last_capture: Image.Image | None = None
        self.last_success = "—"

    # ------------------------------------------------------------------ state
    @property
    def state(self) -> AgentState:
        with self._lock:
            return self._state

    @property
    def busy(self) -> bool:
        return self._request_lock.locked()

    @property
    def monitoring(self) -> bool:
        with self._lock:
            run = self._run
        return run is not None and not run.stop.is_set() and run.thread is not None \
            and run.thread.is_alive()

    @property
    def can_retry(self) -> bool:
        return self._last_payload is not None

    def _emit(self, kind: str, task_id: int | None = None, data: Any = None, **extra) -> None:
        self.events.put(AgentEvent(kind, task_id, data, extra))

    def _transition(self, new: AgentState, detail: str = "") -> bool:
        with self._lock:
            old = self._state
            if new == old:
                return True
            if new not in TRANSITIONS[old]:
                self.logger.warn(f"Ignored invalid state change {old.value} → {new.value}")
                return False
            self._state = new
        self._emit("state", data=new, detail=detail)
        return True

    def apply_settings(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.detector.threshold = settings.change_threshold
        self.detector.settle_time_s = settings.settle_time_s

    # ------------------------------------------------------------------ commands
    def set_mode(self, key: str) -> bool:
        with self._lock:
            if self.monitoring or self.busy or self._state == AgentState.PROCESSING:
                self.logger.warn("Stop the agent before switching modes.")
                return False
            self.mode = MODES[key]
            self._last_payload = None
            self.detector.reset()
            if self._state in (AgentState.WAITING_FOR_REVIEW, AgentState.ERROR, AgentState.STOPPED):
                self._transition(AgentState.IDLE)
        self.logger.info(f"Mode selected: {self.mode.title}")
        return True

    def set_context(self, ctx: ModeContext) -> None:
        self.context = ctx  # atomic reference swap; workers snapshot it per task

    def start(self) -> bool:
        with self._lock:
            if self.monitoring:
                self.logger.warn("Agent is already running — ignored duplicate Start.")
                return False
            if self._state == AgentState.PROCESSING:
                self.logger.warn("Wait for the current request to finish before starting.")
                return False
            if not self._transition(AgentState.RUNNING):
                return False
            self._generation += 1
            run = _Run(self._generation)
            run.resume.set()
            run.thread = threading.Thread(target=self._monitor_loop, args=(run,),
                                          name=f"monitor-{run.generation}", daemon=True)
            self._run = run
            self.detector.reset()
            run.thread.start()
        self.logger.ok(f"Agent started — monitoring every {self.settings.monitor_interval_s:g}s "
                       f"({self.mode.title})")
        return True

    def pause(self) -> bool:
        with self._lock:
            run = self._run
            if not self.monitoring or self._state not in (AgentState.RUNNING, AgentState.PROCESSING):
                return False
            run.resume.clear()
            self._transition(AgentState.PAUSED)
        msg = "Agent paused — no new captures."
        if self.busy:
            msg += " The in-flight request will finish and its result will still be shown."
        self.logger.warn(msg)
        return True

    def resume(self) -> bool:
        with self._lock:
            run = self._run
            if not self.monitoring or self._state not in (AgentState.PAUSED,
                                                           AgentState.WAITING_FOR_REVIEW):
                return False
            if not self._transition(AgentState.RUNNING):
                return False
            run.resume.set()
        self.logger.ok("Agent resumed.")
        return True

    def stop(self) -> bool:
        with self._lock:
            run = self._run
            was_busy = self.busy
            if run is not None:
                run.stop.set()
                run.resume.set()      # wake the loop so it can exit
            self._generation += 1     # any in-flight result is now stale
            if self._state == AgentState.STOPPED:
                return False
            self._transition(AgentState.STOPPED)
        msg = "Agent stopped."
        if was_busy:
            msg += (" A request already sent to Gemini cannot be recalled; "
                    "its result will be discarded.")
        self.logger.warn(msg)
        return True

    def capture_once(self) -> bool:
        return self._start_one_shot(payload=None)

    def analyze_text(self, text: str) -> bool:
        if not text.strip():
            self.logger.warn("Nothing to analyze — paste some text first.")
            return False
        if not self.mode.supports_text_input:
            self.logger.warn(f"{self.mode.title} works from screenshots only.")
            return False
        return self._start_one_shot(payload=(None, ModeContext(text, self.context.study_only),
                                             self.mode))

    def retry(self) -> bool:
        if self._last_payload is None:
            self.logger.warn("Nothing to retry yet.")
            return False
        self.logger.info("Retrying last request…")
        return self._start_one_shot(payload=self._last_payload)

    def clear(self) -> None:
        with self._lock:
            self._last_payload = None
            self.last_capture = None
            if self._state in (AgentState.WAITING_FOR_REVIEW, AgentState.ERROR, AgentState.STOPPED):
                self._transition(AgentState.IDLE)

    def shutdown(self, timeout: float = 1.5) -> None:
        with self._lock:
            run = self._run
        self.stop()
        if run is not None and run.thread is not None and run.thread.is_alive():
            run.thread.join(timeout)

    # ------------------------------------------------------------------ workers
    def _start_one_shot(self, payload) -> bool:
        with self._lock:
            if self.monitoring and self._state != AgentState.PAUSED:
                self.logger.warn("Pause or stop the running agent before a one-off capture.")
                return False
            if self.busy or self._state == AgentState.PROCESSING:
                self.logger.warn("A request is already in progress — ignored.")
                return False
            return_state = AgentState.PAUSED if self.monitoring else AgentState.WAITING_FOR_REVIEW
            if not self._transition(AgentState.PROCESSING):
                return False
            generation = self._generation
        threading.Thread(target=self._one_shot, args=(generation, payload, return_state),
                         name="one-shot", daemon=True).start()
        return True

    def _one_shot(self, generation: int, payload, return_state: AgentState) -> None:
        if payload is None:
            try:
                image_png = self._capture_for_upload()
            except AgentError as err:
                self._report_error(None, err)
                self._finish_one_shot(generation, AgentState.ERROR if return_state !=
                                      AgentState.PAUSED else AgentState.PAUSED)
                return
            payload = (image_png, self.context, self.mode)
        result, err = self._run_analysis(generation, payload)
        if result is not None:
            self._finish_one_shot(generation, return_state)
        else:
            stale = generation != self._generation
            failed = err is not None and err.category != ErrorCategory.CANCELLED
            next_state = AgentState.PAUSED if return_state == AgentState.PAUSED else (
                AgentState.ERROR if failed and not stale else return_state)
            self._finish_one_shot(generation, next_state)

    def _finish_one_shot(self, generation: int, state: AgentState) -> None:
        with self._lock:
            if generation == self._generation and self._state == AgentState.PROCESSING:
                self._transition(state)

    def _capture_for_upload(self) -> bytes:
        self.logger.info("Capturing screen…")
        capture = self.screenshots.capture()
        for warning in capture.warnings:
            self.logger.warn(warning)
        self.last_capture = capture.image
        self._emit("capture", data=capture.image)
        where = capture.region.describe() if capture.region else "full screen"
        self.logger.info(f"Screenshot captured ({where}).")
        return prepare_for_upload(capture.image, self.settings.max_image_side)

    def _run_analysis(self, generation: int, payload) -> tuple[Any, AgentError | None]:
        if not self._request_lock.acquire(blocking=False):
            return None, AgentError(ErrorCategory.CANCELLED, "Another request is in progress.")
        try:
            image_png, ctx, mode = payload
            self._last_payload = payload
            with self._lock:
                self._task_seq += 1
                task_id = self._task_seq
            source = "screenshot" if image_png is not None else "pasted text"
            self._emit("task", task_id, data=mode.key, source=source)
            self.logger.info(f"Task #{task_id}: sending {source} to {self.service.label} "
                             f"({mode.title})…")
            try:
                raw = self.service.analyze(mode.build_request(ctx, image_png),
                                           should_continue=lambda: generation == self._generation)
                self._emit("counter", data=self.service.request_count)
                result = mode.parse(raw)
            except Exception as exc:
                self._emit("counter", data=self.service.request_count)
                err = classify_exception(exc)
                if generation != self._generation:
                    self.logger.info(f"Task #{task_id} ended after it was cancelled — ignored.")
                    return None, err
                self._report_error(task_id, err)
                return None, err
            if generation != self._generation:
                self.logger.warn(f"Discarded stale result from task #{task_id} (agent was "
                                 "stopped or restarted).")
                return None, None
            self.logger.ok(f"Task #{task_id}: response validated — result ready for review.")
            self.last_success = f"Task #{task_id} · {mode.title}"
            self._emit("result", task_id, data=result, mode=mode.key,
                       mock=self.service.is_mock, study_only=ctx.study_only)
            return result, None
        finally:
            self._request_lock.release()

    def _report_error(self, task_id: int | None, err: AgentError) -> None:
        prefix = f"Task #{task_id}: " if task_id else ""
        self.logger.error(f"{prefix}{err.category.value} — {err.message}")
        self._emit("error", task_id, data=err)

    def _monitor_loop(self, run: _Run) -> None:
        last_status: ChangeStatus | None = None
        screenshot_failures = 0
        while not run.stop.is_set():
            run.resume.wait()
            if run.stop.is_set():
                break
            try:
                capture = self.screenshots.capture()
                screenshot_failures = 0
            except AgentError as err:
                screenshot_failures += 1
                if screenshot_failures == 1:
                    self._report_error(None, err)
                if screenshot_failures >= 3:
                    self.logger.error("Repeated screenshot failures — pausing the agent.")
                    with self._lock:
                        if self._run is run and self._state == AgentState.RUNNING:
                            run.resume.clear()
                            self._transition(AgentState.PAUSED)
                run.stop.wait(self.settings.monitor_interval_s)
                continue

            status, signature = self.detector.check(capture.image)
            if status == ChangeStatus.UNCHANGED and last_status != ChangeStatus.UNCHANGED:
                self.logger.info("No relevant change detected — not sending.")
            elif status == ChangeStatus.SETTLING and last_status != ChangeStatus.SETTLING:
                self.logger.info("Screen changed — waiting for it to settle…")
            elif status == ChangeStatus.CHANGED:
                self._process_change(run, capture, signature)
            last_status = status
            run.stop.wait(self.settings.monitor_interval_s)

    def _process_change(self, run: _Run, capture, signature) -> None:
        if self.busy:
            self.logger.info("Previous request still finishing — will check again.")
            return
        with self._lock:
            if run.stop.is_set() or self._state != AgentState.RUNNING:
                return
            self._transition(AgentState.PROCESSING)
        self.logger.info("Meaningful change detected.")
        for warning in capture.warnings:
            self.logger.warn(warning)
        self.last_capture = capture.image
        self._emit("capture", data=capture.image)
        image_png = prepare_for_upload(capture.image, self.settings.max_image_side)
        result, err = self._run_analysis(run.generation, (image_png, self.context, self.mode))
        # Mark processed even on failure: never re-upload the same screen in a loop.
        # The user can always use Retry.
        self.detector.mark_processed(signature)
        with self._lock:
            if self._run is not run or self._state != AgentState.PROCESSING:
                return  # paused/stopped meanwhile: keep that state
            if err is not None and err.category in _PAUSE_CATEGORIES:
                run.resume.clear()
                self._transition(AgentState.PAUSED)
                wait = f" Retry in ~{err.retry_after:.0f}s." if err.retry_after else ""
                self.logger.warn(f"Continuous mode paused because of: {err.category.value}.{wait}")
            elif result is not None and self.mode.pause_for_review:
                run.resume.clear()
                self._transition(AgentState.WAITING_FOR_REVIEW)
                self.logger.info("Paused for your review — press Resume to keep monitoring.")
            else:
                self._transition(AgentState.RUNNING)

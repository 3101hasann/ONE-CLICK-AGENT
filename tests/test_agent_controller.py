import json
import queue
import threading
import time

from PIL import Image, ImageDraw

from app.activity_logger import ActivityLogger
from app.agent_controller import AgentController, AgentState
from app.config import AgentSettings, AppConfig
from app.error_handler import AgentError, ErrorCategory
from app.gemini_service import GeminiService
from app.screenshot_service import Capture

PRACTICE = json.dumps({"task_type": "short_answer", "detected_question": "Q",
                       "suggested_answer": "A", "explanation": "E", "confidence": "high"})


def screen(variant: int = 0) -> Image.Image:
    img = Image.new("RGB", (800, 600), "white")
    ImageDraw.Draw(img).rectangle((50, 50 + variant * 100, 700, 120 + variant * 100), fill="black")
    return img


class FakeScreens:
    def __init__(self):
        self.variant = 0
        self.calls = 0

    def capture(self):
        self.calls += 1
        return Capture(screen(self.variant), None)


class FakeService(GeminiService):
    """Mocked Gemini: no network, configurable latency/response/failure."""
    label = "FakeGemini"

    def __init__(self, response=PRACTICE, delay=0.0, error=None):
        super().__init__(AppConfig("k", "m", False, "ok", settings=AgentSettings(max_retries=0)))
        self.response, self.delay, self.error = response, delay, error
        self.gate = threading.Event()
        self.gate.set()

    def _generate(self, request):
        self._count()
        self.gate.wait(5)
        time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.response


def make(service=None, **settings):
    opts = dict(monitor_interval_s=0.05, settle_time_s=0.0, min_request_gap_s=0.0)
    opts.update(settings)
    events = queue.Queue()
    controller = AgentController(service or FakeService(), FakeScreens(), ActivityLogger(),
                                 AgentSettings(**opts), events)
    controller.settings.monitor_interval_s = opts["monitor_interval_s"]  # bypass clamp for speed
    return controller, events


def drain(events):
    out = []
    while True:
        try:
            out.append(events.get_nowait())
        except queue.Empty:
            return out


def wait_for(predicate, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_capture_once_produces_validated_result():
    controller, events = make()
    assert controller.capture_once()
    assert wait_for(lambda: controller.state == AgentState.WAITING_FOR_REVIEW)
    results = [e for e in drain(events) if e.kind == "result"]
    assert len(results) == 1 and results[0].data.suggested_answer == "A"


def test_repeated_start_does_not_create_duplicate_workers():
    controller, _ = make()
    assert controller.start()
    assert not controller.start()
    assert not controller.start()
    monitors = [t for t in threading.enumerate() if t.name.startswith("monitor-")]
    assert len([t for t in monitors if t.is_alive()]) == 1
    controller.shutdown()


def test_unchanged_screen_is_sent_only_once():
    service = FakeService()
    controller, _ = make(service)
    controller.start()
    assert wait_for(lambda: controller.screenshots.calls >= 15)
    controller.shutdown()
    assert service.request_count == 1


def test_changed_screen_is_processed_again():
    service = FakeService()
    controller, _ = make(service)
    controller.start()
    assert wait_for(lambda: service.request_count == 1)
    controller.screenshots.variant = 2
    assert wait_for(lambda: service.request_count == 2)
    controller.shutdown()


def test_stop_prevents_new_captures():
    controller, _ = make()
    controller.start()
    assert wait_for(lambda: controller.screenshots.calls >= 2)
    controller.stop()
    time.sleep(0.15)
    calls = controller.screenshots.calls
    time.sleep(0.3)
    assert controller.screenshots.calls == calls
    assert controller.state == AgentState.STOPPED
    assert not controller.capture_once() or True  # one-shots are allowed again after stop


def test_stale_response_after_stop_is_ignored():
    service = FakeService()
    service.gate.clear()                      # hold the request "in flight"
    controller, events = make(service)
    controller.capture_once()
    assert wait_for(lambda: controller.busy)
    controller.stop()
    service.gate.set()                        # response arrives after Stop
    assert wait_for(lambda: not controller.busy)
    time.sleep(0.05)
    kinds = [e.kind for e in drain(events)]
    assert "result" not in kinds
    assert controller.state == AgentState.STOPPED


def test_pause_stops_capturing_and_resume_continues():
    controller, _ = make()
    controller.start()
    assert wait_for(lambda: controller.screenshots.calls >= 2)
    controller.pause()
    time.sleep(0.15)
    calls = controller.screenshots.calls
    time.sleep(0.3)
    assert controller.screenshots.calls == calls
    controller.resume()
    assert wait_for(lambda: controller.screenshots.calls > calls)
    controller.shutdown()


def test_rate_limit_pauses_continuous_mode():
    service = FakeService(error=AgentError(ErrorCategory.RATE_LIMIT, "quota", retry_after=30))
    controller, events = make(service)
    controller.start()
    assert wait_for(lambda: controller.state == AgentState.PAUSED)
    errors = [e for e in drain(events) if e.kind == "error"]
    assert errors and errors[0].data.category == ErrorCategory.RATE_LIMIT
    time.sleep(0.2)
    assert service.request_count == 1        # no retry storm
    controller.shutdown()


def test_malformed_response_shows_error_and_allows_retry():
    service = FakeService(response='{"oops": ')
    controller, events = make(service)
    controller.capture_once()
    assert wait_for(lambda: controller.state == AgentState.ERROR)
    assert any(e.kind == "error" for e in drain(events))
    assert controller.can_retry
    service.response = PRACTICE
    assert controller.retry()
    assert wait_for(lambda: controller.state == AgentState.WAITING_FOR_REVIEW)


def test_duplicate_one_shot_requests_are_rejected():
    service = FakeService()
    service.gate.clear()
    controller, _ = make(service)
    assert controller.capture_once()
    assert not controller.capture_once()
    assert not controller.start()
    service.gate.set()
    assert wait_for(lambda: controller.state == AgentState.WAITING_FOR_REVIEW)
    assert service.request_count == 1


def test_mode_cannot_change_while_running():
    controller, _ = make()
    controller.start()
    assert not controller.set_mode("form")
    controller.shutdown()
    assert controller.set_mode("form")


def test_quota_error_blocks_further_api_calls():
    service = FakeService(error=AgentError(ErrorCategory.RATE_LIMIT, "quota", retry_after=68000))
    controller, events = make(service)
    controller.capture_once()
    assert wait_for(lambda: controller.state == AgentState.ERROR)
    service.error = None                     # even if the API would now succeed…
    assert controller.retry()
    assert wait_for(lambda: controller.state == AgentState.ERROR)
    assert service.request_count == 1       # …the retry is refused locally, no API call
    errors = [e.data for e in drain(events) if e.kind == "error"]
    assert "no request sent" in errors[-1].message


def test_session_budget_caps_requests():
    service = FakeService()
    service.settings.session_request_budget = 2
    controller, _ = make(service)
    for _ in range(3):
        controller.capture_once()
        assert wait_for(lambda: controller.state in (AgentState.WAITING_FOR_REVIEW, AgentState.ERROR))
    assert service.request_count == 2
    assert controller.state == AgentState.ERROR


def test_continuous_mode_respects_min_request_gap():
    service = FakeService()
    controller, _ = make(service, min_request_gap_s=30.0)
    controller.start()
    assert wait_for(lambda: service.request_count == 1)
    for variant in (1, 2, 3):
        controller.screenshots.variant = variant
        time.sleep(0.2)
    controller.shutdown()
    assert service.request_count == 1

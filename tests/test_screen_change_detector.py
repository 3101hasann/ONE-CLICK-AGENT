from PIL import Image, ImageDraw

from app.screen_change_detector import ChangeStatus, ScreenChangeDetector


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def page(text_lines: int, cursor_at=None) -> Image.Image:
    img = Image.new("RGB", (1280, 720), "white")
    draw = ImageDraw.Draw(img)
    for i in range(text_lines):
        draw.rectangle((100, 80 + i * 60, 900, 110 + i * 60), fill="black")
    if cursor_at:
        x, y = cursor_at
        draw.polygon([(x, y), (x, y + 18), (x + 12, y + 13)], fill="black")
    return img


def settle(detector, clock, image):
    status, sig = detector.check(image)
    clock.now += 2.0
    status, sig = detector.check(image)
    return status, sig


def test_identical_screenshots_do_not_trigger_reprocessing():
    clock = FakeClock()
    det = ScreenChangeDetector(threshold=0.004, settle_time_s=1.0, clock=clock)
    status, sig = settle(det, clock, page(3))
    assert status == ChangeStatus.CHANGED
    det.mark_processed(sig)
    for _ in range(5):
        clock.now += 2.0
        assert det.check(page(3))[0] == ChangeStatus.UNCHANGED


def test_meaningful_change_is_detected_after_settling():
    clock = FakeClock()
    det = ScreenChangeDetector(threshold=0.004, settle_time_s=1.0, clock=clock)
    det.mark_processed(settle(det, clock, page(3))[1])
    assert det.check(page(6))[0] == ChangeStatus.SETTLING   # debounce first
    clock.now += 1.5
    assert det.check(page(6))[0] == ChangeStatus.CHANGED


def test_cursor_movement_is_ignored():
    clock = FakeClock()
    det = ScreenChangeDetector(threshold=0.004, settle_time_s=0.0, clock=clock)
    det.mark_processed(det.check(page(3, cursor_at=(1000, 500)))[1])
    assert det.check(page(3, cursor_at=(1100, 600)))[0] == ChangeStatus.UNCHANGED


def test_resolution_change_counts_as_change():
    det = ScreenChangeDetector(settle_time_s=0.0)
    det.mark_processed(det.check(page(3))[1])
    assert det.check(page(3).resize((1920, 1080)))[0] == ChangeStatus.CHANGED

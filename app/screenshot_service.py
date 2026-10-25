"""Screen capture and image preparation. Images stay in memory; nothing is written to disk."""
from __future__ import annotations

import io
import threading
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageStat

from app.error_handler import AgentError, ErrorCategory

MIN_SIDE = 40
SMALL_REGION_SIDE = 200


@dataclass(frozen=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)

    def describe(self) -> str:
        return f"{self.width}×{self.height} at ({self.left}, {self.top})"


@dataclass(frozen=True)
class Capture:
    image: Image.Image
    region: Region | None
    warnings: tuple[str, ...] = ()


class ScreenshotService:
    """Captures the primary screen (or a region) and masks out CHEATER.exe's own window."""

    def __init__(self):
        self._lock = threading.Lock()
        self._region: Region | None = None
        self._own_window: tuple[int, int, int, int] | None = None  # x, y, w, h in screen px

    # These setters are called from the UI thread; capture() runs on workers.
    def set_region(self, region: Region | None) -> None:
        with self._lock:
            self._region = region

    @property
    def region(self) -> Region | None:
        with self._lock:
            return self._region

    def set_own_window(self, rect: tuple[int, int, int, int] | None) -> None:
        with self._lock:
            self._own_window = rect

    def capture(self) -> Capture:
        import pyautogui  # imported lazily: it touches the display on import

        with self._lock:
            region, own = self._region, self._own_window
        try:
            screen_w, screen_h = pyautogui.size()
        except Exception as exc:
            raise AgentError(ErrorCategory.SCREENSHOT, "Could not read the screen size.",
                             "Screen capture may be unsupported in this session.") from exc

        warnings: list[str] = []
        if region is not None:
            clipped = _clip(region, screen_w, screen_h)
            if clipped is None:
                raise AgentError(ErrorCategory.SCREENSHOT,
                                 "The selected region is outside the current screen.",
                                 "The resolution may have changed — select the region again.")
            if clipped != region:
                warnings.append("Region was clipped to the current screen bounds.")
            region = clipped
        try:
            image = pyautogui.screenshot(region=region.as_tuple() if region else None)
        except Exception as exc:
            raise AgentError(ErrorCategory.SCREENSHOT, f"Screenshot failed ({type(exc).__name__}).",
                             "Check screen-recording permissions and try again.") from exc

        image = image.convert("RGB")
        if own is not None:
            image = mask_rect(image, own, region)
        validate_image(image)
        if region and min(region.width, region.height) < SMALL_REGION_SIDE:
            warnings.append("Capture region is small — text may be hard to read.")
        return Capture(image=image, region=region, warnings=tuple(warnings))


def _clip(region: Region, screen_w: int, screen_h: int) -> Region | None:
    left, top = max(region.left, 0), max(region.top, 0)
    right = min(region.left + region.width, screen_w)
    bottom = min(region.top + region.height, screen_h)
    if right - left < MIN_SIDE or bottom - top < MIN_SIDE:
        return None
    return Region(left, top, right - left, bottom - top)


def mask_rect(image: Image.Image, rect: tuple[int, int, int, int],
              region: Region | None) -> Image.Image:
    """Black out `rect` (screen coords) so the app never captures or re-triggers on itself."""
    x, y, w, h = rect
    if region is not None:
        x, y = x - region.left, y - region.top
    box = (x, y - 40, x + w, y + h)  # include the native title bar above the client area
    if box[2] <= 0 or box[3] <= 0 or box[0] >= image.width or box[1] >= image.height:
        return image
    image = image.copy()
    ImageDraw.Draw(image).rectangle(box, fill=(0, 0, 0))
    return image


def validate_image(image: Image.Image) -> None:
    if image is None or image.width < MIN_SIDE or image.height < MIN_SIDE:
        raise AgentError(ErrorCategory.SCREENSHOT, "The captured image is empty or too small.",
                         "Select a larger region and recapture.")
    stddev = ImageStat.Stat(image.convert("L")).stddev[0]
    if stddev < 2.0:
        raise AgentError(ErrorCategory.SCREENSHOT,
                         "The capture is blank (one solid colour).",
                         "Move the CHEATER.exe window off the content, or select a region "
                         "that contains the question/form/text.")


def prepare_for_upload(image: Image.Image, max_side: int) -> bytes:
    """Downscale beyond max_side, then JPEG-encode: far smaller + faster than PNG, and the
    model reads text fine at quality 90. Smaller images also mean fewer vision tokens → faster."""
    if max(image.size) > max_side:
        image = image.copy()
        image.thumbnail((max_side, max_side), Image.LANCZOS)
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90, optimize=True, progressive=True)
    return buffer.getvalue()

"""Local screen-change detection, so continuous mode never re-uploads an unchanged screen.

Strategy: downscale to a small grayscale grid (a cursor shrinks to a fraction of one cell),
quantize to absorb anti-aliasing noise, then count cells whose brightness moved by more than
`cell_delta`. A change must also stay stable for `settle_time_s` (debounce) before it is
reported, which filters transient animations and page transitions.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from PIL import Image, ImageFilter

GRID = (96, 64)


class ChangeStatus(str, Enum):
    UNCHANGED = "unchanged"
    SETTLING = "settling"
    CHANGED = "changed"


@dataclass(frozen=True)
class Signature:
    size: tuple[int, int]      # original capture size: a resolution change is always a change
    cells: bytes
    digest: str


def compute_signature(image: Image.Image) -> Signature:
    small = image.convert("L").filter(ImageFilter.BoxBlur(1)).resize(GRID, Image.BILINEAR)
    cells = bytes((v // 8) * 8 for v in small.tobytes())  # quantize to 32 levels
    return Signature(image.size, cells, hashlib.sha1(cells).hexdigest())


def difference(a: Signature, b: Signature, cell_delta: int = 24) -> float:
    """Fraction of grid cells that changed meaningfully (1.0 when sizes differ)."""
    if a.size != b.size:
        return 1.0
    if a.digest == b.digest:
        return 0.0
    changed = sum(1 for x, y in zip(a.cells, b.cells) if abs(x - y) > cell_delta)
    return changed / len(a.cells)


class ScreenChangeDetector:
    def __init__(self, threshold: float = 0.004, settle_time_s: float = 1.0,
                 clock: Callable[[], float] = time.monotonic):
        self.threshold = threshold
        self.settle_time_s = settle_time_s
        self._clock = clock
        self._processed: Signature | None = None
        self._pending: Signature | None = None
        self._pending_since = 0.0

    def reset(self) -> None:
        self._processed = None
        self._pending = None

    def check(self, image: Image.Image) -> tuple[ChangeStatus, Signature]:
        sig = compute_signature(image)
        if self._processed is not None and difference(sig, self._processed) < self.threshold:
            self._pending = None
            return ChangeStatus.UNCHANGED, sig
        now = self._clock()
        if self._pending is None or difference(sig, self._pending) >= self.threshold:
            self._pending, self._pending_since = sig, now   # new (or still moving) content
            if self.settle_time_s > 0:
                return ChangeStatus.SETTLING, sig
        if now - self._pending_since >= self.settle_time_s:
            return ChangeStatus.CHANGED, sig
        return ChangeStatus.SETTLING, sig

    def mark_processed(self, sig: Signature) -> None:
        self._processed = sig
        self._pending = None

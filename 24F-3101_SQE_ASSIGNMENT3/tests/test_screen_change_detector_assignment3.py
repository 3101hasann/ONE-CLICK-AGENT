"""Assignment 3 — unit tests for app/screen_change_detector.py.

Owner: M. Hassan Ahmad (24F-3101).

Covers the two module functions (compute_signature, difference) and the
ScreenChangeDetector class (check / reset / mark_processed). Techniques:
Equivalence Class Partitioning (ECP), Boundary Value Analysis (BVA), decision
testing, parameterization and regression. Boundaries are taken from the source:
GRID = (96, 64) -> 6144 cells; quantization step 8; difference cell_delta = 24
(strict >); detector threshold compared with strict <; settle uses >=.

Test IDs: SCD-xxx (see docs/assignment3/test_design_notes.md).
"""
from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from app.screen_change_detector import (GRID, ChangeStatus, ScreenChangeDetector,
                                         Signature, compute_signature, difference)

pytestmark = [pytest.mark.unit, pytest.mark.screen_detection]

CELL_COUNT = GRID[0] * GRID[1]   # 96 * 64 = 6144


class FakeClock:
    """Deterministic monotonic clock so settle/debounce timing is exact."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def solid(color, size=(1280, 720)) -> Image.Image:
    return Image.new("RGB", size, color)


def page(lines: int, size=(1280, 720)) -> Image.Image:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    for i in range(lines):
        draw.rectangle((100, 80 + i * 60, 900, 110 + i * 60), fill="black")
    return img


def sig_of(*byte_values, size=(10, 10), digest="d"):
    """Build a Signature directly, to drive difference() boundaries precisely."""
    return Signature(size, bytes(byte_values), digest)


# --------------------------------------------------------------- compute_signature
@pytest.mark.smoke
def test_signature_preserves_original_size():
    sig = compute_signature(solid("white", (800, 600)))
    assert sig.size == (800, 600)


def test_signature_has_one_byte_per_grid_cell():
    assert len(compute_signature(page(3)).cells) == CELL_COUNT


def test_signature_cells_are_quantized_to_multiples_of_eight():
    # cells = (v // 8) * 8, so every byte must be a multiple of 8.
    assert all(byte % 8 == 0 for byte in compute_signature(page(5)).cells)


def test_identical_images_have_identical_digest():
    assert compute_signature(page(3)).digest == compute_signature(page(3)).digest


def test_different_images_have_different_digest():
    assert compute_signature(page(3)).digest != compute_signature(page(8)).digest


def test_digest_is_sha1_hex():
    sig = compute_signature(page(2))
    assert len(sig.digest) == 40 and all(c in "0123456789abcdef" for c in sig.digest)


# --------------------------------------------------------------- difference (ECP/BVA)
def test_difference_is_zero_for_identical_signature():
    sig = compute_signature(page(3))
    assert difference(sig, sig) == 0.0


def test_difference_zero_when_digests_match_even_if_cells_scanned():
    a = sig_of(10, 10, 10, digest="same")
    b = sig_of(250, 250, 250, digest="same")   # same digest short-circuits to 0.0
    assert difference(a, b) == 0.0


@pytest.mark.parametrize("size_a,size_b", [((10, 10), (10, 11)), ((1280, 720), (1920, 1080)),
                                           ((100, 100), (99, 100))])
def test_difference_is_one_when_sizes_differ(size_a, size_b):
    a = Signature(size_a, bytes([0] * 4), "a")
    b = Signature(size_b, bytes([0] * 4), "b")
    assert difference(a, b) == 1.0


@pytest.mark.parametrize("delta,expected_changed", [(23, 1.0), (24, 0.0), (25, 0.0)])
def test_difference_cell_delta_boundary_is_strict_greater_than(delta, expected_changed):
    # Two cells differ by exactly 24. Default cell_delta=24 uses strict '>',
    # so a 24-difference is NOT counted; 23 is.
    a = sig_of(100, 100, digest="a")
    b = sig_of(124, 124, digest="b")
    assert difference(a, b, cell_delta=delta) == expected_changed


def test_difference_counts_full_change_as_one():
    a = sig_of(*([0] * 100), digest="a")
    b = sig_of(*([255] * 100), digest="b")
    assert difference(a, b) == 1.0


def test_difference_returns_fraction_for_partial_change():
    # 25 of 100 cells move by 48 (> 24); the rest are identical.
    a = sig_of(*([100] * 100), digest="a")
    b = sig_of(*([148] * 25 + [100] * 75), digest="b")
    assert difference(a, b) == pytest.approx(0.25)


# --------------------------------------------------------------- detector behavior
def make_detector(threshold=0.004, settle_time_s=1.0):
    clock = FakeClock()
    return ScreenChangeDetector(threshold, settle_time_s, clock), clock


@pytest.mark.smoke
def test_first_change_reports_settling_when_debounced():
    det, _ = make_detector(settle_time_s=1.0)
    status, _ = det.check(page(3))
    assert status == ChangeStatus.SETTLING


def test_change_is_reported_after_settle_time_elapses():
    det, clock = make_detector(settle_time_s=1.0)
    det.check(page(3))               # arms pending at t=0
    clock.advance(1.0)
    assert det.check(page(3))[0] == ChangeStatus.CHANGED


@pytest.mark.parametrize("elapsed,expected", [(0.99, ChangeStatus.SETTLING),
                                              (1.0, ChangeStatus.CHANGED),
                                              (1.5, ChangeStatus.CHANGED)])
def test_settle_timing_boundary(elapsed, expected):
    det, clock = make_detector(settle_time_s=1.0)
    det.check(page(4))               # pending armed at t=0
    clock.advance(elapsed)
    assert det.check(page(4))[0] == expected


def test_zero_settle_time_reports_change_immediately():
    det, _ = make_detector(settle_time_s=0.0)
    assert det.check(page(3))[0] == ChangeStatus.CHANGED


def test_processed_identical_screen_is_unchanged():
    det, clock = make_detector(settle_time_s=0.0)
    det.mark_processed(det.check(page(3))[1])
    assert det.check(page(3))[0] == ChangeStatus.UNCHANGED


def test_meaningful_change_after_processed_is_detected():
    det, _ = make_detector(settle_time_s=0.0)
    det.mark_processed(det.check(page(3))[1])
    assert det.check(page(10))[0] == ChangeStatus.CHANGED


def test_resolution_change_counts_as_change():
    det, _ = make_detector(settle_time_s=0.0)
    det.mark_processed(det.check(page(3))[1])
    assert det.check(page(3).resize((1920, 1080)))[0] == ChangeStatus.CHANGED


def test_reset_clears_processed_and_pending_state():
    det, _ = make_detector(settle_time_s=0.0)
    det.mark_processed(det.check(page(3))[1])
    assert det.check(page(3))[0] == ChangeStatus.UNCHANGED
    det.reset()
    # After reset there is no processed baseline, so the same screen is "changed" again.
    assert det.check(page(3))[0] == ChangeStatus.CHANGED


def test_small_change_below_threshold_is_unchanged():
    # A high threshold makes a modest change fall below it -> treated as unchanged.
    clock = FakeClock()
    det = ScreenChangeDetector(threshold=0.9, settle_time_s=0.0, clock=clock)
    det.mark_processed(det.check(page(3))[1])
    assert det.check(page(4))[0] == ChangeStatus.UNCHANGED

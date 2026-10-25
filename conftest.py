"""Shared pytest configuration for ONE-CLICK-AGENT (Assignment 3).

Two things happen here:

1. Auto-markers — so the existing regression tests in ``tests/*.py`` are not
   edited: every test under ``tests/unit`` or ``tests/data`` is tagged
   ``assignment3``; everything else is tagged ``regression``.

2. Deterministic group order — ``pytest_collection_modifyitems`` sorts the
   collected tests by group so a plain ``pytest`` run executes them in the
   documented order: smoke -> config -> validation -> screen_detection ->
   csv_data -> regression. Tests stay independent, so parallel runs
   (``-n auto``) may interleave groups; only the sequential order is fixed.
"""
from __future__ import annotations

# The per-member submission packages hold copies of these tests; exclude them
# from the root run so the same test file is never collected twice.
collect_ignore_glob = ["24F-*_SQE_ASSIGNMENT3/*", "24F-*_SQE_ASSIGNMENT3/**/*"]

# Order in which test groups run during a sequential execution.
GROUP_ORDER = ["smoke", "config", "validation", "screen_detection", "csv_data", "regression"]


def pytest_collection_modifyitems(config, items):
    # 1) Auto-apply the broad group markers by location.
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/tests/unit/" in path or "/tests/data/" in path:
            item.add_marker("assignment3")
        else:
            item.add_marker("regression")

    # 2) Stable sort into the documented group order.
    def rank(item):
        names = {m.name for m in item.iter_markers()}
        for index, group in enumerate(GROUP_ORDER):
            if group in names:
                return index
        return len(GROUP_ORDER)

    items.sort(key=rank)

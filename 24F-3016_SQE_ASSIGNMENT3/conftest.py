"""Submission-package conftest.

This folder is a self-contained copy of one member's Assignment 3 work. The
application source (the ``app`` package) lives in the project root two levels up,
so this file puts the project root on ``sys.path`` and then applies the same
group ordering as the main suite. Run the tests from inside this folder:

    python -m pytest
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # this folder -> project root (has app/)
sys.path.insert(0, str(PROJECT_ROOT))

GROUP_ORDER = ["smoke", "config", "validation", "screen_detection", "csv_data"]


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker("assignment3")

    def rank(item):
        names = {m.name for m in item.iter_markers()}
        for index, group in enumerate(GROUP_ORDER):
            if group in names:
                return index
        return len(GROUP_ORDER)

    items.sort(key=rank)

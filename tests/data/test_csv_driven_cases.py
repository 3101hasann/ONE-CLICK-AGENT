"""Assignment 3 — Task 3: data-driven tests that read an external CSV file.

The test inputs come from tests/data/assignment3_test_data.csv (not hard-coded
here). Each row has:

    test_id,module,function,target,input,expected,technique,member

Rows are grouped by (module, function) and fed into pytest.mark.parametrize, so
each CSV record becomes its own executable test case whose id is the row's
test_id. Four CSV-driven test functions consume the file:

    * config / clamp               -> AgentSettings.clamp() boundaries
    * response_models / confidence -> FormField.confidence normalization
    * response_models / chosen_index -> FeedbackQuestion.chosen_index coercion
    * screen_change_detector / difference -> difference() cell_delta boundary

test_csv_file_is_wellformed validates the header and that every row parses,
which is where malformed rows would be reported.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.config import AgentSettings
from app.response_models import FeedbackQuestion, FormField
from app.screen_change_detector import Signature, difference

pytestmark = [pytest.mark.csv_data]

CSV_PATH = Path(__file__).parent / "assignment3_test_data.csv"
EXPECTED_HEADER = ["test_id", "module", "function", "target", "input", "expected",
                   "technique", "member"]


def _load_rows():
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _num(text: str):
    """Parse a CSV cell to int or float when it is numeric, else return the string."""
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _cases(module: str, function: str):
    """Return (id, row) pairs for one (module, function) group, read from the file."""
    rows = [r for r in _load_rows() if r["module"] == module and r["function"] == function]
    return [pytest.param(r, id=r["test_id"]) for r in rows]


def test_csv_file_exists_and_is_consumed():
    assert CSV_PATH.exists(), f"missing CSV data file: {CSV_PATH}"
    assert len(_load_rows()) >= 4


def test_csv_file_is_wellformed():
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        assert header == EXPECTED_HEADER
        for line_no, row in enumerate(reader, start=2):
            assert len(row) == len(EXPECTED_HEADER), f"malformed row at line {line_no}: {row}"
            assert row[0].strip(), f"empty test_id at line {line_no}"


@pytest.mark.parametrize("row", _cases("config", "clamp"))
def test_clamp_from_csv(row):
    settings = AgentSettings()
    setattr(settings, row["target"], _num(row["input"]))
    settings.clamp()
    assert getattr(settings, row["target"]) == pytest.approx(_num(row["expected"]))


@pytest.mark.parametrize("row", _cases("response_models", "confidence"))
def test_confidence_from_csv(row):
    field = FormField(label="csv", confidence=_num(row["input"]))
    assert field.confidence == pytest.approx(_num(row["expected"]))


@pytest.mark.parametrize("row", _cases("response_models", "chosen_index"))
def test_chosen_index_from_csv(row):
    # CSV cells are strings, so pass the raw string to exercise string coercion:
    # "3" -> 3, "2.5" -> int("2.5") fails -> -1, "x" -> -1.
    question = FeedbackQuestion(question="csv", chosen_index=row["input"])
    assert question.chosen_index == int(row["expected"])


@pytest.mark.parametrize("row", _cases("screen_change_detector", "difference"))
def test_difference_cell_delta_from_csv(row):
    # Two signatures whose cells differ by exactly 24; cell_delta comes from the CSV.
    a = Signature((10, 10), bytes([100] * 50), "a")
    b = Signature((10, 10), bytes([124] * 50), "b")
    result = difference(a, b, cell_delta=int(row["input"]))
    assert result == pytest.approx(_num(row["expected"]))

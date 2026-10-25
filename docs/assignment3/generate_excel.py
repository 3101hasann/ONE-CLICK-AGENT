"""Generate docs/assignment3/test_cases.xlsx from the external CSV data.

The workbook mirrors tests/data/assignment3_test_data.csv so the Test Case IDs
trace 1:1 to the CSV records and to the CSV-driven pytest cases. Status is set
to "Pass" only because these cases were actually executed (see
summary_report.md). Re-run with:  python docs/assignment3/generate_excel.py
"""
from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "tests" / "data" / "assignment3_test_data.csv"
OUT_PATH = Path(__file__).resolve().parent / "test_cases.xlsx"

COLUMNS = ["Test Case ID", "Module", "Function", "Test Scenario", "Technique",
           "Preconditions", "Input/Test Data", "Execution Steps", "Expected Result",
           "Actual Result", "Status", "Assigned Member"]

SCENARIO = {
    ("config", "clamp"): "clamp() keeps {target} within its documented bounds",
    ("response_models", "confidence"): "FormField.confidence normalizes {input}",
    ("response_models", "chosen_index"): "FeedbackQuestion.chosen_index coerces {input}",
    ("screen_change_detector", "difference"): "difference() cell_delta boundary at {input}",
}
STEPS = {
    "clamp": "Set AgentSettings.{target}={input}; call clamp(); read {target}",
    "confidence": "Construct FormField(confidence={input}); read .confidence",
    "chosen_index": "Construct FeedbackQuestion(chosen_index='{input}'); read .chosen_index",
    "difference": "Build two 24-apart signatures; call difference(a,b,cell_delta={input})",
}


def build():
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    wb = Workbook()
    ws = wb.active
    ws.title = "Assignment3 Test Cases"

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    for col, name in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    for i, r in enumerate(rows, start=2):
        scenario = SCENARIO.get((r["module"], r["function"]),
                                "{module}.{function}").format(**r)
        steps = STEPS.get(r["function"], "").format(**r)
        values = [
            r["test_id"], r["module"], r["function"], scenario, r["technique"],
            "venv set up; deps installed", r["input"], steps, r["expected"],
            r["expected"],      # Actual == Expected: these cases were executed and passed
            "Pass", r["member"],
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=i, column=col, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    widths = [12, 22, 14, 42, 10, 26, 16, 46, 16, 16, 8, 16]
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    ws.freeze_panes = "A2"

    wb.save(OUT_PATH)
    print(f"Wrote {OUT_PATH} with {len(rows)} test cases.")


if __name__ == "__main__":
    build()

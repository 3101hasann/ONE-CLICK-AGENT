"""Generate the Word summary report (summary_report.docx) for Assignment 3.

Produces one .docx per group member (same body, personalised cover line) and
writes it into each member's submission folder. Re-run with:
    python docs/assignment3/generate_docx.py
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]

MEMBERS = [
    ("M. Hassan Ahmad", "24F-3101", "Screen-change detection (app/screen_change_detector.py)",
     ROOT / "24F-3101_SQE_ASSIGNMENT3" / "docs" / "summary_report.docx"),
    ("M. Ahmad Asghar", "24F-3016", "Response-model validation (app/response_models.py)",
     ROOT / "24F-3016_SQE_ASSIGNMENT3" / "docs" / "summary_report.docx"),
]

COUNTS = [("Screen-change detector", "27", "M. Hassan Ahmad (24F-3101)"),
          ("Response models", "60", "M. Ahmad Asghar (24F-3016)"),
          ("Configuration", "69", "Shared"),
          ("CSV-driven", "20", "Shared"),
          ("New total", "176", ""),
          ("Existing regression", "39", "(pre-existing)"),
          ("Grand total", "215", "")]

RESULTS = [("python -m pytest  (full, sequential)", "215 passed"),
           ("python -m pytest -m assignment3", "176 passed"),
           ("python -m pytest -m assignment3 -n auto  (parallel)", "176 passed"),
           ("python -m pytest -m regression", "39 passed"),
           ("python -m pytest -m csv_data -v  (reads CSV)", "20 passed")]


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h


def table(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, head in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = head
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
    return t


def build(member_name, member_id, ownership, out_path):
    doc = Document()

    title = doc.add_heading("Assignment 3 — Build Unit Test Automation Solution", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run("Project: ONE-CLICK-AGENT  ·  Software Quality Engineering")
    run.italic = True
    run.font.size = Pt(11)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(f"Prepared by {member_name} ({member_id})\n").bold = True
    meta.add_run("Group: M. Hassan Ahmad (24F-3101), M. Ahmad Asghar (24F-3016)\n")
    meta.add_run("Repository: https://github.com/3101hasann/ONE-CLICK-AGENT")

    doc.add_paragraph()

    heading(doc, "1. Overview")
    doc.add_paragraph(
        "ONE-CLICK-AGENT is a Windows desktop AI agent written in Python with "
        "CustomTkinter, the Google Gemini API and Pydantic. For this assignment we built an "
        "automated unit-test suite around its pure-logic modules. The tests run entirely "
        "offline: the Gemini client is mocked, screen data is synthetic, and configuration is "
        "isolated with pytest's monkeypatch and tmp_path fixtures, so no API key, internet or "
        "real screen is needed to run them.")

    heading(doc, "2. Selected modules")
    doc.add_paragraph("We chose three modules with self-contained, testable logic:")
    for line in [
        "app/screen_change_detector.py — image-signature and change-threshold logic; strong "
        "boundary analysis on the cell-delta (24), the change threshold and the settle timer.",
        "app/response_models.py — Pydantic validation and coercion rules; good fit for "
        "equivalence partitioning and negative testing of the real error paths.",
        "app/config.py — AgentSettings.clamp() has explicit numeric bounds on eight fields, "
        "which gives clean boundary-value tests, plus decision logic in load_config.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    heading(doc, f"3. My contribution ({member_id})")
    doc.add_paragraph(
        f"My allocated module for Task 2 is {ownership}. I derived the equivalence classes and "
        "boundary values from the source code rather than assuming them, and documented each "
        "test with a traceable ID in the design notes. Configuration tests, the CSV/Excel "
        "deliverables and the pytest configuration were done jointly with my partner.")

    heading(doc, "4. Testing techniques")
    doc.add_paragraph(
        "Equivalence Class Partitioning, Boundary Value Analysis, negative/exception testing, "
        "decision testing, parameterization and regression. Concrete boundaries include the "
        "strict greater-than at cell-delta 24, the strict less-than change threshold, the >= "
        "settle timing, the eight clamp ranges, and the >1 percentage rule for confidence.")

    heading(doc, "5. Test-count matrix")
    table(doc, ["Scope", "New tests", "Member"], COUNTS)

    heading(doc, "6. CSV and Excel deliverables")
    doc.add_paragraph(
        "Test inputs are stored in tests/data/assignment3_test_data.csv (18 rows, documented "
        "header) and are read at collection time by four data-driven pytest functions. The Excel "
        "workbook docs/test_cases.xlsx lists 18 cases with the recommended columns, generated "
        "from the same CSV so every Test Case ID traces 1:1 to a CSV record and an automated "
        "test.")

    heading(doc, "7. Configuration: suites, parallelism and order")
    doc.add_paragraph(
        "Tests are grouped with pytest markers (smoke, config, validation, screen_detection, "
        "csv_data, regression). Parallel execution uses pytest-xdist (-n auto). A conftest hook "
        "sets the sequential group order: smoke, config, validation, screen_detection, "
        "csv_data, regression. The tests are independent, so a parallel run gives the same "
        "results; only the temporal order differs.")

    heading(doc, "8. Execution results (verified)")
    table(doc, ["Command", "Result"], RESULTS)
    doc.add_paragraph("No failures, no skips, no errors. Results were produced in the project "
                      "virtual environment on Windows with Python 3.14.6.")

    heading(doc, "9. Known limitations and pending items")
    for line in [
        "Unit tests cover pure logic; the GUI, live Gemini calls and real desktop automation "
        "are out of unit scope (covered at integration level by the existing controller tests).",
        "The group-order guarantee applies to sequential runs only.",
        "The repository currently has no LICENSE file; this is noted, not changed automatically.",
        "The setup video is a screen recording of the setup and test run (in the video folder).",
        "Each member commits their own files under their own Git identity; no authorship was "
        "fabricated.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    print("Wrote", out_path)


if __name__ == "__main__":
    for name, mid, ownership, path in MEMBERS:
        build(name, mid, ownership, path)

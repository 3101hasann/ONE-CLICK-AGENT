"""Generate a complete Assignment 3 guide as a PDF.

Covers: what the assignment asks, who did what, the three modules, test counts,
techniques, CSV/Excel, configuration, setup + run commands, folder layout,
verified results, and what is left to do. Output goes to docs/assignment3/ and is
copied into both member folders. Re-run:
    python docs/assignment3/make_guide_pdf.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (ListFlowable, ListItem, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "Assignment3_Complete_Guide.pdf"

NAVY = colors.HexColor("#1F4E78")
LIGHT = colors.HexColor("#EAF1F8")
CODEBG = colors.HexColor("#F3F3F3")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H1b", parent=styles["Heading1"], textColor=NAVY, spaceBefore=12,
                          spaceAfter=6, fontSize=15))
styles.add(ParagraphStyle("H2b", parent=styles["Heading2"], textColor=NAVY, fontSize=12,
                          spaceBefore=8, spaceAfter=3))
styles.add(ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14,
                          spaceAfter=5))
styles.add(ParagraphStyle("Small", parent=styles["BodyText"], fontSize=9, leading=12))
styles.add(ParagraphStyle("TitleBig", parent=styles["Title"], textColor=NAVY, fontSize=22))
styles.add(ParagraphStyle("Center", parent=styles["BodyText"], alignment=TA_CENTER, fontSize=11))
styles.add(ParagraphStyle("CodeBlk", parent=styles["Code"], fontSize=8.5, leading=11,
                          backColor=CODEBG, borderPadding=5, leftIndent=2))

story = []


def h1(t): story.append(Paragraph(t, styles["H1b"]))
def h2(t): story.append(Paragraph(t, styles["H2b"]))
def p(t): story.append(Paragraph(t, styles["Body"]))
def small(t): story.append(Paragraph(t, styles["Small"]))
def code(t): story.append(Preformatted(t, styles["CodeBlk"]))
def gap(h=4): story.append(Spacer(1, h))


def bullets(items):
    story.append(ListFlowable([ListItem(Paragraph(x, styles["Body"]), leftIndent=10)
                               for x in items], bulletType="bullet", start="disc"))


def table(data, widths, header=True):
    t = Table(data, colWidths=widths, hAlign="LEFT")
    style = [("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("FONTSIZE", (0, 0), (-1, -1), 8.5),
             ("LEFTPADDING", (0, 0), (-1, -1), 4),
             ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT])]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    story.append(t)


# ---------------------------------------------------------------- cover
story.append(Spacer(1, 40))
story.append(Paragraph("Assignment 3", styles["TitleBig"]))
story.append(Paragraph("Build Unit Test Automation Solution — Complete Guide", styles["Center"]))
gap(16)
story.append(Paragraph("Project: <b>ONE-CLICK-AGENT</b>", styles["Center"]))
story.append(Paragraph("github.com/3101hasann/ONE-CLICK-AGENT", styles["Center"]))
gap(10)
story.append(Paragraph("<b>Group members</b>", styles["Center"]))
story.append(Paragraph("M. Hassan Ahmad — 24F-3101", styles["Center"]))
story.append(Paragraph("M. Ahmad Asghar — 24F-3016", styles["Center"]))
gap(10)
story.append(Paragraph("Course: Software Quality Engineering", styles["Center"]))
story.append(PageBreak())

# ---------------------------------------------------------------- 1. overview
h1("1. What Assignment 3 asks for")
p("The assignment is about <b>automated unit testing</b>. We take our Python project and write "
  "small programs (tests) that call the project's functions with known inputs and check the "
  "outputs are correct. All tests run with one command (<font face='Courier'>pytest</font>). "
  "If anyone later breaks the code, a test fails and warns us.")
p("The marked tasks are:")
table([["Task", "Marks", "What it means"],
       ["Task 1", "5", "Set up the project locally and record a short setup video."],
       ["Task 2", "40", "Pick 3 modules; write 5-10 unit tests per function using ECP/BVA; commit notes."],
       ["Task 3", "10", "Put >=4 test cases in Excel and read test data from an external CSV file."],
       ["Task 4", "10", "Configure test groups, parallel runs, parameterization and an execution order."],
       ["Summary", "3", "A summary report before the due date."],
       ["Distribution", "2", "Git history must show each member's individual work."]],
      [55, 35, 370])

# ---------------------------------------------------------------- 2. allocation
h1("2. Team roles and task allocation")
p("Task 1, Task 3, Task 4 and the summary are shared. Task 2 (the big one) is split so each "
  "member owns a different module and can be graded individually.")
table([["Member", "Owns (Task 2)", "Their tests", "Also did (shared)"],
       ["M. Hassan Ahmad (24F-3101)", "app/screen_change_detector.py", "27 tests",
        "config tests, CSV/Excel, pytest config, docs"],
       ["M. Ahmad Asghar (24F-3016)", "app/response_models.py", "60 tests",
        "config tests, CSV/Excel, pytest config, docs"]],
      [120, 150, 55, 135])
gap(6)
p("<b>Separate submission folders</b> (each self-contained) were created in the project:")
bullets(["<font face='Courier'>24F-3101_SQE_ASSIGNMENT3/</font> — Hassan's package (116 tests)",
         "<font face='Courier'>24F-3016_SQE_ASSIGNMENT3/</font> — Ahmad's package (149 tests)"])

# ---------------------------------------------------------------- 3. modules
h1("3. The three modules under test")
h2("3.1 app/screen_change_detector.py  (Hassan)")
p("Decides whether the screen changed enough to re-send to the AI, so the app never re-uploads "
  "an unchanged screen. Functions tested: <font face='Courier'>compute_signature</font> (shrinks "
  "an image to a 96x64 grayscale fingerprint), <font face='Courier'>difference</font> (how much "
  "two fingerprints differ), and the <font face='Courier'>ScreenChangeDetector</font> class "
  "(check / reset / mark_processed). Key boundary: a cell counts as 'changed' only when its "
  "brightness moves by more than 24 (strict greater-than).")
h2("3.2 app/response_models.py  (Ahmad)")
p("Validates the structured responses from the AI before the app trusts them. Tested: "
  "<font face='Courier'>parse_model_output</font> (accepts good JSON, rejects empty/broken "
  "input), <font face='Courier'>FormField.confidence</font> (a value above 1 is treated as a "
  "percentage and clamped to 0-1), and <font face='Courier'>FeedbackQuestion</font> coercion "
  "for the chosen option index and click coordinates (kept only within 0-1000).")
h2("3.3 app/config.py  (shared)")
p("Loads settings and keeps them within safe limits. The main target is "
  "<font face='Courier'>AgentSettings.clamp()</font>, which bounds eight numeric settings — "
  "ideal for boundary testing (below-min, at-min, middle, at-max, above-max). Also tested: "
  "<font face='Courier'>AppConfig.problem</font>, <font face='Courier'>load_config</font> "
  "(reading environment variables) and settings save/load.")

# ---------------------------------------------------------------- 4. counts
h1("4. Test-count matrix")
table([["Module / scope", "Function area", "New tests", "Member"],
       ["screen_change_detector", "compute_signature / difference / detector", "27", "Hassan"],
       ["response_models", "parse / confidence / coercion / defaults", "60", "Ahmad"],
       ["config", "clamp / problem / load_config / settings I/O", "69", "Shared"],
       ["CSV-driven", "4 data-driven functions", "20", "Shared"],
       ["New total", "", "176", ""],
       ["Existing regression", "preserved, unchanged", "39", "pre-existing"],
       ["GRAND TOTAL", "", "215", ""]],
      [140, 180, 55, 80])
small("Each parametrized case counts as one test (this is how pytest reports them). Every "
      "selected function has at least 5 tests, meeting the 5-10 requirement.")

# ---------------------------------------------------------------- 5. techniques
h1("5. Testing techniques used")
bullets([
    "<b>ECP (Equivalence Class Partitioning)</b> — one example from each category of input "
    "(valid, invalid, missing).",
    "<b>BVA (Boundary Value Analysis)</b> — the edges: e.g. clamp ranges tested at below-min, "
    "min, mid, max, above-max; cell_delta at 23/24/25.",
    "<b>Negative / exception testing</b> — broken JSON, wrong types, out-of-range values.",
    "<b>Decision testing</b> — the config 'problem' table (mock / no key / no model / ok).",
    "<b>Parameterization</b> — one test function runs many input cases.",
    "<b>Regression</b> — the original 39 tests are kept and still pass."])

# ---------------------------------------------------------------- 6. task3
h1("6. Task 3 — Excel and CSV")
p("<b>CSV:</b> <font face='Courier'>tests/data/assignment3_test_data.csv</font> holds 18 rows of "
  "test inputs. Four test functions read this file at run time and turn each row into a test "
  "(config clamp, confidence, chosen_index, and the difference boundary).")
p("<b>Excel:</b> <font face='Courier'>docs/assignment3/test_cases.xlsx</font> lists 18 documented "
  "cases with columns (ID, Module, Function, Scenario, Technique, Input, Steps, Expected, Actual, "
  "Status, Member). It is generated from the same CSV so every ID traces 1:1.")

# ---------------------------------------------------------------- 7. task4
h1("7. Task 4 — Groups, parallel and order")
p("Configured in <font face='Courier'>pytest.ini</font> and <font face='Courier'>conftest.py</font>.")
bullets([
    "<b>Groups (markers):</b> smoke, config, validation, screen_detection, csv_data, regression.",
    "<b>Parallel:</b> <font face='Courier'>pytest -n auto</font> (pytest-xdist).",
    "<b>Parameterization:</b> used across all files.",
    "<b>Order:</b> smoke -> config -> validation -> screen_detection -> csv_data -> regression "
    "(sequential runs; parallel may interleave, which is fine because tests are independent)."])

# ---------------------------------------------------------------- 8. setup
h1("8. Setup commands (one time)")
code("cd C:\\Users\\Hassan\\cheater-exe\n"
     "python -m venv .venv\n"
     ".venv\\Scripts\\Activate.ps1\n"
     "pip install -r requirements.txt\n"
     "pip install -r requirements-dev.txt")
small("If activation is blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned. "
      "Tests need no API key or internet.")

# ---------------------------------------------------------------- 9. running
h1("9. Running the tests")
h2("Everything / assignment / parallel")
code("python -m pytest                 # whole project  -> 215 passed\n"
     "python -m pytest -m assignment3  # our new tests   -> 176 passed\n"
     "python -m pytest -n auto         # parallel        -> 215 passed\n"
     "python -m pytest -v              # show every test name")
h2("Only MY work (Hassan, 24F-3101)")
code("python -m pytest -m screen_detection   # my 27 tests (individual Task 2)\n"
     "cd 24F-3101_SQE_ASSIGNMENT3 & ..\\.venv\\Scripts\\python.exe -m pytest   # my folder -> 116")
h2("Only AHMAD's work (24F-3016)")
code("python -m pytest -m validation         # his 60 tests (individual Task 2)\n"
     "cd 24F-3016_SQE_ASSIGNMENT3 & ..\\.venv\\Scripts\\python.exe -m pytest   # his folder -> 149")
h2("By group / by file / CSV")
code("python -m pytest -m config            # 69\n"
     "python -m pytest -m csv_data -v       # 20 (reads the CSV)\n"
     "python -m pytest tests/unit/test_config_assignment3.py\n"
     "python -m pytest --collect-only -q    # see the run order")

# ---------------------------------------------------------------- 10. layout
h1("10. Folder layout")
code("cheater-exe/\n"
     "  app/                      the application being tested\n"
     "  tests/                    live test suite (runs the whole project)\n"
     "    test_*.py               existing regression tests (39)\n"
     "    unit/                   new assignment tests (config, validation, screen)\n"
     "    data/                   CSV + CSV-driven tests\n"
     "  pytest.ini, conftest.py   markers, parallel, ordering config\n"
     "  requirements-dev.txt      pytest-xdist, openpyxl\n"
     "  docs/assignment3/         all docs, Excel, this guide\n"
     "  24F-3101_SQE_ASSIGNMENT3/ Hassan's submission package (tests, docs, video)\n"
     "  24F-3016_SQE_ASSIGNMENT3/ Ahmad's submission package (tests, docs, video)")

# ---------------------------------------------------------------- 11. results
h1("11. Verified results")
table([["Command", "Result"],
       ["python -m pytest (full, sequential)", "215 passed"],
       ["python -m pytest -n auto (parallel)", "215 passed"],
       ["python -m pytest -m assignment3", "176 passed"],
       ["Hassan folder (24F-3101)", "116 passed"],
       ["Ahmad folder (24F-3016)", "149 passed"],
       ["python -m pytest -m csv_data", "20 passed (reads CSV)"]],
      [330, 180])
small("No failures, no skips, no errors. Run in the project venv on Windows, Python 3.14.6.")

# ---------------------------------------------------------------- 12. todo
h1("12. What is still to be done (by the group)")
bullets([
    "Each member commits their own files under their own Git identity (see "
    "member_contributions.md) so the history shows individual work.",
    "Push to GitHub when ready, make the repository public, and submit the link on GCR.",
    "Setup videos are included (terminal recordings of the real test runs); re-record as a "
    "desktop screencast if the evaluator requires it (script in setup_video_script.md).",
    "The repository has no LICENSE file (left as-is by decision); noted in the docs."])

# ---------------------------------------------------------------- 13. checklist
h1("13. Deliverables checklist")
table([["Deliverable", "File(s)", "Status"],
       ["Setup guide", "docs/.../setup_guide.md", "Done"],
       ["Setup video + script", "video/*.mp4, setup_video_script.md", "Done"],
       ["Unit tests (3 modules)", "tests/unit/*.py", "Done (176)"],
       ["Test inventory + matrix", "test_inventory.md", "Done"],
       ["ECP/BVA design notes", "test_design_notes.md", "Done"],
       ["Excel workbook", "test_cases.xlsx", "Done (18)"],
       ["External CSV + driven tests", "tests/data/*", "Done (4 funcs)"],
       ["Pytest config (groups/parallel/order)", "pytest.ini, conftest.py", "Done"],
       ["Execution guide", "test_execution_guide.md", "Done"],
       ["Member contributions", "member_contributions.md", "Done"],
       ["Summary report (md + Word)", "summary_report.md/.docx", "Done"],
       ["This complete guide", "Assignment3_Complete_Guide.pdf", "Done"]],
      [185, 230, 75])

doc = SimpleDocTemplate(str(OUT), pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                        leftMargin=18 * mm, rightMargin=16 * mm,
                        title="Assignment 3 — Complete Guide", author="24F-3101, 24F-3016")
doc.build(story)
print("Wrote", OUT)

for mid in ("24F-3101", "24F-3016"):
    dest = ROOT / f"{mid}_SQE_ASSIGNMENT3" / "docs" / OUT.name
    shutil.copy(OUT, dest)
    print("Copied to", dest)

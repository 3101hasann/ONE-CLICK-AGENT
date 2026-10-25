# Assignment 3 — Unit Test Automation (24F-3016)

**Member:** M. Ahmad Asghar — 24F-3016
**Group partner:** M. Hassan Ahmad — 24F-3101
**Project:** ONE-CLICK-AGENT — https://github.com/3101hasann/ONE-CLICK-AGENT

This folder is my submission package. It holds the test code I am responsible
for, the shared configuration and data tests, and all the assignment documents.
The application source it tests lives in the project root (the `app/` package).

## My Task 2 ownership

I own the **response-model validation** module:

- Source under test: `app/response_models.py`
- My test file: `tests/test_response_models_assignment3.py` — **60 tests**
- My design notes: the **RM-###** section of `docs/test_design_notes.md`

I applied Equivalence Class Partitioning, Boundary Value Analysis and negative
testing to the Pydantic validation and coercion rules. The main behaviours I
tested are `parse_model_output` (valid/invalid/empty input classes), the
`FormField.confidence` normalization (values above 1 treated as a percentage,
then clamped to [0, 1]), and the `FeedbackQuestion` coercion for `chosen_index`
and the click coordinates (kept only within 0–1000, else -1).

## Shared work in this folder

Per the rubric, Task 1 (setup), Task 3 (Excel/CSV), Task 4 (configuration) and
the summary report are shared. Included here:

- `tests/test_config_assignment3.py` — configuration tests (shared)
- `tests/test_csv_driven_cases.py` + `tests/assignment3_test_data.csv` — CSV-driven tests
- `docs/` — setup guide, inventory, design notes, execution guide, summary (md + docx), compliance, and the Excel workbook `test_cases.xlsx`
- `video/` — my setup / test-run recording

## How to run (from inside this folder)

```powershell
# from the project root first, set up the venv and install deps (see docs/setup_guide.md)
cd 24F-3016_SQE_ASSIGNMENT3
python -m pytest            # runs config + csv + validation tests
python -m pytest -v         # verbose, shows each test id
python -m pytest -n auto    # parallel
python -m pytest -m validation   # just my module
```

Expected here: config (69) + csv (20) + validation (60) = **149 passed**.

The full combined suite (both members + the existing regression tests, 215
passed) runs from the project root with `python -m pytest`.

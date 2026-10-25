# Assignment 3 — Unit Test Automation (24F-3101)

**Member:** M. Hassan Ahmad — 24F-3101
**Group partner:** M. Ahmad Asghar — 24F-3016
**Project:** ONE-CLICK-AGENT — https://github.com/3101hasann/ONE-CLICK-AGENT

This folder is my submission package. It holds the test code I am responsible
for, the shared configuration and data tests, and all the assignment documents.
The application source it tests lives in the project root (the `app/` package).

## My Task 2 ownership

I own the **screen-change detection** module:

- Source under test: `app/screen_change_detector.py`
- My test file: `tests/test_screen_change_detector_assignment3.py` — **27 tests**
- My design notes: the **SCD-###** section of `docs/test_design_notes.md`

I applied Equivalence Class Partitioning and Boundary Value Analysis to the
signature logic and the change thresholds. The key boundaries I derived from the
source are the `cell_delta = 24` strict-greater-than comparison in `difference`,
the strict-less-than change `threshold`, and the `>=` settle/debounce timing in
`ScreenChangeDetector.check`.

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
cd 24F-3101_SQE_ASSIGNMENT3
python -m pytest            # runs config + csv + screen-detection tests
python -m pytest -v         # verbose, shows each test id
python -m pytest -n auto    # parallel
python -m pytest -m screen_detection   # just my module
```

Expected here: config (69) + csv (20) + screen-detection (27) = **116 passed**.

The full combined suite (both members + the existing regression tests, 215
passed) runs from the project root with `python -m pytest`.

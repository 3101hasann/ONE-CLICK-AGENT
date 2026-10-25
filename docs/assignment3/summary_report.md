# Assignment 3 — Summary Report

**Project:** ONE-CLICK-AGENT (desktop AI agent, formerly CHEATER.exe)
**Repository:** https://github.com/3101hasann/ONE-CLICK-AGENT
**Group:** M. Hassan Ahmad (24F-3101), M. Ahmad Asghar (24F-3016)

This report summarizes the unit-test automation work. It separates **verified**
results (actually executed) from **pending** items (manual group actions).

## 1. Project overview

ONE-CLICK-AGENT is a Windows desktop AI agent written in Python with
CustomTkinter, the Google Gemini API and Pydantic. It reads the screen, sends a
clean screenshot to Gemini, validates the structured response, and shows it in a
sidebar. The codebase is modular, which makes several components unit-testable in
isolation without the network or a real screen.

## 2. Environment and setup

- Python 3.14.6, Windows 11, virtual environment at `.venv`.
- Runtime deps: `requirements.txt`. Test deps: `requirements-dev.txt`
  (`pytest`, `pytest-xdist` for parallel runs, `openpyxl` for the Excel sheet).
- Unit tests need **no** API key, internet, live browser or real desktop:
  Gemini is mocked, screen data is synthetic, config is isolated with
  `monkeypatch`/`tmp_path`. Full steps in `setup_guide.md`.

## 3. Selected modules and rationale

| Module | Why selected |
|---|---|
| `app/screen_change_detector.py` | Pure signature/threshold logic → strong BVA on cell-delta (24), settle time and threshold. |
| `app/response_models.py` | Pydantic validation/coercion rules → ECP + negative testing of real error paths. |
| `app/config.py` | `clamp()` has explicit numeric bounds on 8 fields → textbook BVA; env/settings loading is decision logic. |

Modules tied to threads, the Gemini client, PyAutoGUI or Tk (`agent_controller`,
`gemini_service`, `automation_service`, `ui`) are already covered at the
integration level by the existing suite and are less suitable for isolated unit
BVA/ECP. Rationale detailed in `test_inventory.md`.

## 4. Test design techniques

ECP, BVA, negative/exception testing, decision testing, parameterization and
regression. Every boundary was derived from the source (e.g. `cell_delta` strict
`>` at 24; threshold strict `<`; settle `>=`; clamp bounds; confidence `>1`
treated as a percentage). Full mapping with Test IDs in `test_design_notes.md`.

## 5. Test-count matrix (verified by `pytest --collect-only`)

| Scope | New tests | Member |
|---|---:|---|
| screen_change_detector | 27 | Hassan (24F-3101) |
| response_models | 60 | Ahmad (24F-3016) |
| config | 69 | Shared |
| CSV-driven | 20 | Shared |
| **New total** | **176** | |
| Existing regression | 39 | (pre-existing) |
| **Grand total** | **215** | |

Marker counts: smoke 5, config 69, validation 60, screen_detection 27,
csv_data 20, assignment3 176, regression 39.

## 6. Existing vs newly added tests

The 39 existing tests in `tests/*.py` were preserved unchanged and are
auto-marked `regression`. The 176 new tests live in `tests/unit/` and
`tests/data/`. Nothing was deleted or weakened to get a green result.

## 7. CSV and Excel deliverables

- **CSV:** `tests/data/assignment3_test_data.csv` (18 rows, header documented).
  Consumed by **four** data-driven test functions in
  `tests/data/test_csv_driven_cases.py`, which read the file at collection time.
- **Excel:** `docs/assignment3/test_cases.xlsx` — 18 documented cases with the
  recommended columns, generated from the CSV so IDs trace 1:1
  (`generate_excel.py`). Status is "Pass" because these cases were executed.

## 8. Parallel execution, grouping and ordering

- **Groups/suites:** pytest markers in `pytest.ini`; `conftest.py` auto-marks
  assignment vs regression and enforces group order.
- **Parallel:** `pytest -n auto` (pytest-xdist). Verified to pass.
- **Parameterization:** used throughout (clamp BVA, confidence, coercion, CSV).
- **Order:** sequential order is smoke → config → validation → screen_detection
  → csv_data → regression. Under `-n auto` the temporal order is not guaranteed;
  tests are independent, so results are unaffected. See `test_execution_guide.md`.

## 9. Actual test execution results (verified)

Run in `.venv` on Windows, `python -m pytest`:

| Command | Result |
|---|---|
| `python -m pytest` (full, sequential) | **215 passed** |
| `python -m pytest -m assignment3` | **176 passed** |
| `python -m pytest -m assignment3 -n auto` (parallel) | **176 passed** |
| `python -m pytest -m regression` | **39 passed** |
| `python -m pytest -m csv_data -v` | **20 passed** (reads the CSV) |

No failures, no skips, no xfails. (Exact console output is reproducible with the
commands in `test_execution_guide.md`.)

## 10. Known limitations

- Unit tests cover pure logic; the GUI, live Gemini calls and real desktop
  automation are intentionally out of unit scope (covered at integration level
  by the existing controller tests).
- The execution order is only guaranteed in sequential runs.
- The repository has **no LICENSE file**; this is noted, not silently fixed.

## 11. Member responsibilities

See `member_contributions.md`. Summary: Hassan owns the screen-detector suite,
Ahmad owns the response-model suite, and config/CSV/Excel/config-files/docs are
shared. Each member commits their own files under their own Git identity; no
authorship was fabricated.

## 12. Setup-video status

**Not yet recorded.** Script and exact recording steps are in
`setup_video_script.md`. The group must record it and add the file to the repo,
then update this section.

## 13. Repository and submission checklist

- [x] Three modules' automated unit tests (176) — verified passing
- [x] Test inventory + per-member matrix
- [x] ECP/BVA design notes with Test IDs
- [x] Excel workbook (18 cases)
- [x] External CSV consumed by 4 automated tests
- [x] Pytest config: suites, markers, parallelism, parameterization, ordering
- [x] Setup guide + execution guide
- [x] Member contribution + Git workflow doc
- [x] Summary report (this file)
- [ ] Setup video recorded and committed (group action)
- [ ] Per-member commits under each identity (group action)
- [ ] Repo made public + link submitted on GCR (group action)
- [ ] Due-date conflict confirmed with instructor (PDF says Oct 21, 2026)
- [ ] LICENSE decision (optional; currently none)

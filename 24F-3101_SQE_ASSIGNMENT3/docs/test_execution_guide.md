# Test Execution Guide — Assignment 3

All commands run from the repository root with the virtual environment active
(or replace `python` with `.venv\Scripts\python.exe`). Configuration lives in
`pytest.ini`; auto-markers and ordering live in `conftest.py`.

## Suites, groups and markers

Markers are registered in `pytest.ini` (`--strict-markers` is on, so a typo in a
marker name fails fast):

| Marker | Meaning | Count |
|---|---|---:|
| `smoke` | fast sanity checks, run first | 5 |
| `config` | `app/config.py` tests | 69 |
| `validation` | `app/response_models.py` tests | 60 |
| `screen_detection` | `app/screen_change_detector.py` tests | 27 |
| `csv_data` | CSV-driven data tests | 20 |
| `assignment3` | all new assignment tests (auto) | 176 |
| `regression` | pre-existing suite (auto) | 39 |

`assignment3` is auto-applied to everything under `tests/unit` and `tests/data`;
`regression` is auto-applied to the existing `tests/*.py` without editing them.

## Common commands

```powershell
# everything (regression + assignment)  -> 215 passed
python -m pytest

# only the assignment tests  -> 176
python -m pytest -m assignment3

# only the existing regression suite  -> 39
python -m pytest -m regression

# one module's tests
python -m pytest tests/unit/test_config_assignment3.py
python -m pytest tests/unit/test_response_models_assignment3.py
python -m pytest tests/unit/test_screen_change_detector_assignment3.py

# one marked group
python -m pytest -m config
python -m pytest -m validation
python -m pytest -m screen_detection
python -m pytest -m smoke

# CSV-driven tests (reads tests/data/assignment3_test_data.csv)
python -m pytest -m csv_data -v
python -m pytest tests/data/test_csv_driven_cases.py -v
```

## Parallel vs sequential

```powershell
# parallel: one worker per CPU core (pytest-xdist)
python -m pytest -n auto

# parallel on the assignment tests only
python -m pytest -m assignment3 -n auto

# sequential (default; also forces xdist off explicitly)
python -m pytest -p no:xdist
```

Parallel runs give the same pass/fail results because the tests are
independent (no shared mutable state, temp files via `tmp_path`, env via
`monkeypatch`). See the ordering note below.

## Test reports

```powershell
# short summary of all outcomes
python -m pytest -ra

# JUnit XML (attachable evidence; generated, not committed)
python -m pytest -ra --junitxml=docs/assignment3/report.xml
```

## Execution order

`conftest.py` sorts collected tests into this sequential order:

1. `smoke`
2. `config`
3. `validation`
4. `screen_detection`
5. `csv_data`
6. `regression`

This is a deliberate strategy: quick smoke checks first, then the pure-logic
unit groups (configuration and validation), then screen-detection, then the
data-driven CSV tests, and finally the broader regression suite.

**Important:** this ordering applies to a *sequential* run. Under `-n auto`,
pytest-xdist distributes tests across workers, so the temporal order is not
guaranteed — groups may interleave. The tests are written to be order- and
worker-independent, so correctness does not depend on the order; only the
sequential, human-readable run follows the list above.

To confirm the order:
```powershell
python -m pytest --collect-only -q
```

## Selecting by keyword / id

```powershell
# every clamp test (unit + CSV-driven)
python -m pytest -k clamp

# a single CSV case by its id
python -m pytest "tests/data/test_csv_driven_cases.py::test_clamp_from_csv[CSV-004]"
```

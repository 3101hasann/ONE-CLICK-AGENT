# Setup Guide (Windows) — ONE-CLICK-AGENT

This guide sets up the project locally on Windows and runs both the existing
test suite and the Assignment 3 tests. The unit tests do **not** need a Gemini
API key, internet access, or a real screen — Gemini, screen capture and the GUI
are mocked or driven with synthetic data.

The commands below were run on Windows 11 with **Python 3.14.6** in a virtual
environment at `.venv`.

## 1. Prerequisites

- Windows 10/11.
- Python **3.11 or newer** (tested on 3.14). Check with:
  ```powershell
  python --version
  ```
  If Python is missing, install it from https://www.python.org/downloads/ and
  tick "Add python.exe to PATH" during setup.
- Git.

## 2. Get the code

```powershell
git clone https://github.com/3101hasann/ONE-CLICK-AGENT.git
cd ONE-CLICK-AGENT
```

## 3. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation with an execution-policy error, run this once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
Or skip activation entirely and call the venv Python directly, e.g.
`.venv\Scripts\python.exe -m pytest`.

## 4. Install dependencies

Runtime dependencies plus the test/dev dependencies (pytest-xdist for parallel
runs, openpyxl for the Excel workbook):

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 5. Create a local `.env` (only needed to RUN the app, not the tests)

```powershell
copy .env.example .env
notepad .env
```

In `.env`, set your key. **Never commit this file** — it is listed in
`.gitignore`:

```
GEMINI_API_KEY=your_real_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_THINKING_LEVEL=minimal
```

Get a key from https://aistudio.google.com/apikey. To explore the UI without a
key, set `CHEATER_MOCK_MODE=1` instead (results are clearly labelled MOCK).

### Keeping the key secure
- The key lives only in the local `.env`; `.gitignore` already excludes `.env`.
- It is never printed in logs (the activity logger redacts keys) and never
  appears in test output — the tests use fake keys and mocked services.
- For the standalone build, keep a `.env` next to `One-Click.exe`.

## 6. Run the application

```powershell
python main.py
```
The app starts hidden behind the floating "Cook" button. (This step needs a real
key or `CHEATER_MOCK_MODE=1`.)

## 7. Run the tests

All tests (existing regression + Assignment 3), no API key required:
```powershell
python -m pytest
```
Expected: **215 passed** (39 existing + 176 new).

Only the Assignment 3 tests:
```powershell
python -m pytest -m assignment3
```

A single module's tests:
```powershell
python -m pytest tests/unit/test_screen_change_detector_assignment3.py
```

One marked group (see groups in `pytest.ini`):
```powershell
python -m pytest -m config
python -m pytest -m validation
python -m pytest -m screen_detection
python -m pytest -m csv_data
python -m pytest -m smoke
```

## 8. Run tests in parallel

```powershell
python -m pytest -n auto
```
`-n auto` uses one worker per CPU core (pytest-xdist). Tests are independent, so
results are identical to a sequential run; only timing differs.

Sequential (default, documented order):
```powershell
python -m pytest -p no:xdist
```

## 9. CSV-driven tests

```powershell
python -m pytest tests/data/test_csv_driven_cases.py -v
```
These read `tests/data/assignment3_test_data.csv` at collection time.

## 10. Produce a test report

```powershell
python -m pytest -ra --junitxml=docs/assignment3/report.xml
```
`-ra` prints a short summary of all outcomes; the JUnit XML can be attached as
evidence. (`report.xml` is a generated artifact and does not need to be
committed.)

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Reinstall Python with "Add to PATH", or use the full path. |
| Activation blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or call `.venv\Scripts\python.exe` directly. |
| `ModuleNotFoundError: app` | Run pytest from the repository root (where `app/` lives). |
| `No module named pytest_xdist` / `-n` unknown | `pip install -r requirements-dev.txt`. |
| `ModuleNotFoundError: openpyxl` | `pip install -r requirements-dev.txt` (only needed to regenerate the Excel). |
| Tests pass but app won't start | Running the app needs a key or `CHEATER_MOCK_MODE=1`; the tests do not. |
| `'copy' is not recognized` | Use PowerShell (not Git Bash) for `copy`, or `Copy-Item .env.example .env`. |

## License note

The repository currently has **no `LICENSE` file**. For the assignment, "open
source" is taken to mean a public repository. Adding a license (for example MIT)
is an ownership decision for the authors and was intentionally not done
automatically.

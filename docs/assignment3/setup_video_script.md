# Setup Video — Script and Recording Instructions

**Status: NOT YET RECORDED.** This file is the script and the exact steps. The
group must record the actual video and add the file to the repository (for
example `docs/assignment3/setup_video.mp4`). Do not mark this deliverable
complete until the video exists in the repo.

Target length: **2–3 minutes**. Tools: any screen recorder (Xbox Game Bar
`Win+G`, OBS Studio, or ScreenToGif for a lightweight clip).

## What to show (checklist)

1. The cloned repo open in a terminal at the project root.
2. Creating and activating the virtual environment.
3. Installing dependencies.
4. Creating `.env` from `.env.example` (show that the key is NOT shown on
   screen / is blurred — never reveal a real key).
5. Running the full test suite and the result line (`215 passed`).
6. Running one marked group and the parallel run.
7. Briefly opening the Excel workbook to show the test cases.

## Spoken script (suggested)

> "This is ONE-CLICK-AGENT, our Assignment 3 project. I'll set it up on Windows
> and run the tests.
>
> First I create a virtual environment with `python -m venv .venv` and activate
> it. Then I install the dependencies: `pip install -r requirements.txt` and
> `pip install -r requirements-dev.txt`, which adds pytest-xdist for parallel
> runs and openpyxl for the Excel sheet.
>
> The unit tests don't need an API key, but to run the app you copy
> `.env.example` to `.env` and paste your Gemini key — I'm keeping mine hidden.
>
> Now the tests. `python -m pytest` runs everything: 39 existing regression
> tests plus our 176 new tests — 215 passed. I can run just our tests with
> `-m assignment3`, a single group like `-m config`, and in parallel with
> `-n auto`. The CSV-driven tests read `assignment3_test_data.csv`.
>
> Finally, here is the Excel workbook with the documented test cases. That's the
> setup and a green test run."

## Exact commands to run on camera

```powershell
git clone https://github.com/3101hasann/ONE-CLICK-AGENT.git
cd ONE-CLICK-AGENT
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
copy .env.example .env      # paste key off-camera; do not show it
python -m pytest            # expect: 215 passed
python -m pytest -m assignment3
python -m pytest -n auto
python -m pytest tests/data/test_csv_driven_cases.py -v
```

## After recording

- Save as `docs/assignment3/setup_video.mp4` (or `.gif` if small).
- Confirm the file plays.
- Commit it to the repo and update `summary_report.md` → "Setup-video status"
  to "recorded and committed", with the filename.

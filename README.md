# ⚡ CHEATER.exe — The One-Click Agent

**One click. One agent. Less busywork.**

CHEATER.exe is a Windows desktop AI agent. Pick a mode and click **Capture Once** or **Start Agent**. It reads what's on your screen, sends it to Google Gemini for analysis, validates the structured result, and shows it in a review panel. Any action, such as copying or typing into a field, needs your confirmation first.

> Built for **practice** and **permitted** tasks only. It never submits anything for you. It flags screens that look like live graded or proctored tests and disables answer entry on them. A **Study-only** switch hides answers and gives hints instead.

---

## About the project

*CHEATER.exe is a one-click desktop AI agent that reads your screen and solves practice questions, fills forms and improves your writing — fast, validated, and always under your control.*

CHEATER.exe — The One-Click Agent is a Windows desktop AI assistant that cuts repetitive screen work down to one click. You pick a mode and click Capture: it reads what's on your screen, sends it to Google Gemini, and shows a structured, validated result in a clean dark dashboard. It has three modes: a **Practice Quiz Solver** that explains and answers practice questions, a **Smart Form Filler** that fills forms using only the details you provide, and **Instant Feedback** that corrects and improves your writing. In continuous mode it watches the screen and sends a request only when the content actually changes. It runs one request at a time and protects your API quota with request limits and automatic pausing. You stay in control: every answer is a reviewed suggestion, nothing is typed without your confirmation, forms are never submitted automatically, and sensitive fields like passwords are never filled. It's built in Python with CustomTkinter, the Gemini API and Pydantic validation, has 39 automated tests, and comes with full UML and data-flow design documentation.

---

## Features

| Mode | What it does |
|---|---|
| ✔ **Practice Quiz Solver** | Transcribes the question and its options, then gives a suggested answer, an explanation, and a confidence level. Study-only mode returns hints instead of answers. |
| ✎ **Smart Form Filler** | Finds the visible form fields and maps **only the details you typed** onto them. You review, edit, and tick each field before anything is entered. Nothing is ever submitted. |
| ✉ **Instant Feedback** | Works on a screenshot or on pasted text. Returns grammar, clarity, and structure feedback plus an improved version that keeps your meaning. |

**One-Click Agent engine** (shared by all modes)
- **Capture Once** or **continuous monitoring** (Start / Pause / Resume / Stop)
- **Local screen-change detection**, so an unchanged screen is never re-uploaded. It uses a downscaled, quantized grayscale grid, which ignores cursor movement, plus a settle/debounce timer.
- Only **one in-flight request** at a time. Each task gets an ID, and results that arrive after Stop or a restart are **discarded as stale**.
- The app **blacks out its own window** in every capture, so it never analyzes itself or re-triggers on its own log.
- **Region selection** (drag a rectangle), and **Preview** to see exactly what would be sent
- **Pydantic validation** of every AI response. Malformed output is rejected and you get a Retry option.
- **Readable error categories**: rate limit/quota, auth, model not found, timeout, network, server, empty, malformed, screenshot, automation
- **Quota protection** (free-tier keys have small daily limits):
  - After a quota/rate-limit error, **no request is sent** until Gemini's reset time. Retry is refused locally, and the wait is shown in plain units (e.g. "~19.0 h").
  - A **per-session request budget** (default 20). The agent pauses when it's used up.
  - In continuous mode, **at most one request every 20 s**, and only for changes larger than 2% of the screen.
  - **No automatic retries** by default, because every attempt counts against your quota. Use Retry manually.
- A timestamped **activity log**. API keys and e-mail addresses are redacted, and no screenshots or form values are logged.
- A footer showing Gemini connection status, mode, monitoring state, and the API request count

## Architecture

```
main.py                      entry point + dependency check
app/
  ui.py                      CustomTkinter UI (widgets only; drains an event queue)
  theme.py                   design tokens (colours, fonts, button styles)
  agent_controller.py        state machine, workers, de-dup, stale-result protection
  screenshot_service.py      capture, region clipping, self-masking, validation, PNG prep
  screen_change_detector.py  local change detection + debounce
  gemini_service.py          google-genai client, timeouts, retries, request counter, MOCK
  modes.py                   mode registry (prompt + schema + post-processing + copy)
  practice_mode.py / form_mode.py / feedback_mode.py   prompts and per-mode rules
  response_models.py         Pydantic schemas + safe parsing
  automation_service.py      allow-listed actions only (copy, paste-into-focused, Tab)
  error_handler.py           error categories + exception translation
  activity_logger.py         thread-safe log with redaction
  config.py                  .env + settings.json
tests/                       unit tests with a mocked Gemini service (no network, no quota)
demo/                        local practice page, sample form, sample texts
```

Background threads never touch widgets. They post `AgentEvent`s to a queue, and the UI drains it on the Tk main loop.

AI output can never trigger arbitrary actions. The only desktop actions are clipboard copy, pasting a value into the field **you** focused, and pressing Tab. Every one runs after an explicit confirmation and a 3-second countdown.

## Design documentation

The full set of design diagrams is in [`docs/`](docs/README.md): the agent orchestrator, data flow diagrams (levels 0–2), the use case diagram, system sequence diagrams (SSD), sequence diagrams (SD), the UML class diagram, the state machine, activity diagrams, and component & deployment diagrams. GitHub renders them inline, and pre-rendered SVGs are in [`docs/images/`](docs/images/).

## Requirements

- Windows 10/11 (macOS/Linux mostly work; window-focus checks are Windows-oriented)
- Python **3.11+** (tested on 3.14)
- A Gemini API key from https://aistudio.google.com/apikey

## Quick start (Windows)

**Option A: double-click `run.bat`.** On first run it creates the virtual environment, installs dependencies, and opens Notepad so you can paste your `GEMINI_API_KEY` into `.env`. After that it launches the app with no console window. Later runs start instantly.

**Option B: standalone `CHEATER.exe`** (no Python needed on the target PC):

```powershell
build_exe.bat          # produces dist\CHEATER.exe (~37 MB)
```

Put a `.env` file containing `GEMINI_API_KEY` **next to `CHEATER.exe`**. `build_exe.bat` copies your local `.env` there automatically. Settings and logs are also stored next to the exe.

## Setup (Windows PowerShell)

```powershell
cd cheater-exe
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env        # set GEMINI_API_KEY (and optionally GEMINI_MODEL)
python main.py
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activation and run `.venv\Scripts\python main.py`.

### Environment variables (`.env`)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | yes | – | Never committed (`.env` is git-ignored) and never logged |
| `GEMINI_MODEL` | no | `gemini-3.8-flash` | Any image-capable model available to your project |
| `GEMINI_THINKING_LEVEL` | no | `low` | `minimal`/`low`/`medium`/`high` (Gemini 3.x). Lower is faster. |
| `CHEATER_MOCK_MODE` | no | off | `1` = canned responses, clearly labelled **MOCK — NOT REAL AI** |
| `CHEATER_MOCK_SCENARIO` | no | `ok` | `rate_limit`, `timeout`, `malformed`: for demoing error handling |

Agent tuning (monitor interval, change sensitivity, settle time, max image size, timeout, retries, minimum gap between requests, session request budget) lives under **⚙ Settings** and is saved to `settings.json`.

## How to use

1. **Practice:** open `demo/practice_question.html` in a browser. Select **Practice Quiz Solver** and click **◎ Capture Once**. Read the suggested answer, confidence, and explanation, then use **Copy**. For a hands-free run, click **Start Agent** and then **Next question →** in the page. Only the changed screen gets analyzed.
2. **Form:** open `demo/sample_form.html` and paste the contents of `demo/my_details_example.txt` into **Your details**. Click **Capture Once**, then review each row: edit values and tick the fields you want filled. Confident, user-sourced values are pre-ticked; uncertain ones are not, and sensitive fields like the password can never be filled. Click **Fill ticked fields** and click into the first ticked field during the countdown. The form is never submitted.
3. **Feedback:** paste `demo/feedback_sample.txt` into the text box and click **Analyze Pasted Text**, or capture text on screen. Then **Copy** the improved version.
4. **Error handling demo:** set `CHEATER_MOCK_MODE=1` and `CHEATER_MOCK_SCENARIO=rate_limit` (or `malformed`). Capture once to see the readable error, the paused agent, and the Retry button, while the UI stays responsive.

**Saving quota:** **Start Agent** sends the current screen right away, then only real changes. Prefer **Capture Once** when you just need one answer, and select a region so unrelated activity (chat apps, videos, clocks) can't trigger requests.

**Tips:** use **Select Region** to send less of your screen; it's faster and more private. Keep the CHEATER.exe window off the content you capture, because it's blacked out in screenshots. To abort typing, press **Stop** or move the mouse into a screen corner (PyAutoGUI fail-safe).

## Privacy & safety

- Screenshots are sent to Google Gemini **only when a task runs**. They live in memory only and are never written to disk. **Clear Results** discards them.
- The activity log contains short event descriptions only. Keys and e-mail addresses are redacted.
- The form filler never invents personal data. Deterministic guards strip any name, e-mail, phone, or date the model didn't get from you, and passwords, cards, IDs, OTPs, and CAPTCHAs are never filled.
- Text in screenshots is treated as untrusted data. Prompts tell the model to ignore instructions embedded in the screen.
- Nothing is ever submitted automatically, and there are no hidden or stealth modes.

## Tests

```powershell
.venv\Scripts\python -m pytest -q
```

The tests cover change detection (identical screens, real changes, cursor movement, resolution change), response validation (malformed, missing, or invalid fields), form safety (uncertain and sensitive fields not auto-filled), error translation (429, 401, 404, 503, timeout), missing configuration, and controller behaviour: duplicate Start, Stop, Pause/Resume, stale results, rate-limit pause, retry, and de-duplication. Gemini is mocked in all of them.

## Known limitations

- Captures the **primary monitor** only.
- Form filling relies on the page's **Tab order**. Sequential fill stops before selects, radios, and checkboxes, which you fill by hand. "Entered" means the keystrokes were sent; check the result on screen.
- An already-sent Gemini request can't be recalled. After Stop its result is discarded.
- Response time depends on Gemini load. Use a smaller region or `GEMINI_THINKING_LEVEL=minimal` for speed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "GEMINI_API_KEY is not set" | Create `.env` from `.env.example`, then restart |
| "model was not found" | Set `GEMINI_MODEL` to a model your key can use (e.g. `gemini-3.8-flash`) |
| Rate limit / quota | The app blocks requests until the reset time it shows. For a daily limit, either wait, switch `GEMINI_MODEL` to another model (quotas are usually per model), or use a key with billing. Check usage in AI Studio |
| "Session limit … reached" | The per-session budget protects your quota. Raise it in ⚙ Settings or restart the app |
| Timeouts / 503 / 504 | Gemini is overloaded or the network is slow. Retry, capture a smaller region, or raise the timeout in Settings |
| "The capture is blank" | Move the CHEATER.exe window off the content, or select a region |
| Nothing typed | Click into the target field during the countdown. CHEATER.exe refuses to type into itself |
| `Missing dependencies` | `pip install -r requirements.txt` inside the venv |

@echo off
rem CHEATER.exe launcher: sets up everything on first run, then starts the app.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.11+ is required. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    python -m venv .venv || (echo Could not create the virtual environment. & pause & exit /b 1)
)

rem Reinstall dependencies only when requirements.txt changes.
fc /b requirements.txt .venv\installed-requirements.txt >nul 2>nul
if errorlevel 1 (
    echo [2/3] Installing dependencies - first run takes a minute...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (echo Dependency install failed. Check your internet connection. & pause & exit /b 1)
    copy /y requirements.txt .venv\installed-requirements.txt >nul
)

if not exist ".env" (
    echo [3/3] No .env found - creating one. Paste your GEMINI_API_KEY, save, and close Notepad.
    copy /y .env.example .env >nul
    notepad .env
)

start "" ".venv\Scripts\pythonw.exe" main.py
endlocal

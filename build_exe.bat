@echo off
rem Builds a standalone dist\One-Click.exe (no Python needed on the target PC).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call run.bat
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q pyinstaller || exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name One-Click --icon app\icon.ico ^
    --add-data "app\icon.ico;app" ^
    --collect-data customtkinter ^
    --collect-submodules google.genai ^
    main.py || (echo Build failed. & pause & exit /b 1)
copy /y .env.example dist\.env.example >nul
if exist .env if not exist dist\.env copy /y .env dist\.env >nul
echo.
echo Built dist\One-Click.exe  - keep a .env file (with GEMINI_API_KEY) next to it.
endlocal

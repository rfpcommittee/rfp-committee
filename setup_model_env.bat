@echo off
cd /d "%~dp0"
rem COMET (unbabel-comet) does not install on Python 3.13/3.14, so this builds a Python 3.12 environment (.venv).
rem It installs the libraries only; the COMET model itself is downloaded from Hugging Face the first time the app
rem runs with USE_MODEL=true.
py -3.12 -m venv .venv
if errorlevel 1 (
    echo Python 3.12 was not found. Install it, or edit this file to use py -3.11.
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo Done. Set USE_MODEL=true in .env, then start the app with run_app.bat

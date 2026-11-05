@echo off
setlocal
cd /d "%~dp0"
rem Builds the Python 3.12 environment (.venv) and installs requirements.txt. COMET (unbabel-comet) does not install on
rem Python 3.13/3.14. Only the libraries are installed here; the COMET model itself is downloaded from Hugging Face the
rem first time the app runs with USE_MODEL=true. Any failed step stops the script with exit code 1.
rem Add the argument "nopause" to skip the "press a key" prompt (used by the tests).

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    set "MSG=ERROR: Python 3.12 was not found. Install it from https://www.python.org/downloads/ and run this file again."
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 (
        set "MSG=ERROR: the .venv environment could not be created."
        goto :fail
    )
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)"
if errorlevel 1 (
    set "MSG=ERROR: .venv uses an unsupported Python (3.10 to 3.12 is needed). Delete the .venv folder and run this file again."
    goto :fail
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    set "MSG=ERROR: pip could not be updated. Check the network and run this file again."
    goto :fail
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    set "MSG=ERROR: the libraries in requirements.txt were not installed. Check the network and run this file again."
    goto :fail
)

".venv\Scripts\python.exe" -m pip check
if errorlevel 1 (
    set "MSG=ERROR: pip check found conflicting library versions (see above)."
    goto :fail
)

".venv\Scripts\python.exe" -c "import streamlit, pandas, sacrebleu, sentencepiece, comet"
if errorlevel 1 (
    set "MSG=ERROR: the libraries were installed but could not be imported (see above)."
    goto :fail
)

echo.
echo Setup finished. All libraries import correctly.
echo Set USE_MODEL=true in .env to include COMET, then start the app with run_app.bat
if /i not "%~1"=="nopause" pause
exit /b 0

:fail
echo.
echo %MSG%
if /i not "%~1"=="nopause" pause
exit /b 1

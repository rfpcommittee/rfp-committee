@echo off
setlocal
cd /d "%~dp0"
rem Starts the app with the .venv made by setup_model_env.bat if it exists, otherwise with the default Python.
rem It first checks that the core libraries import, so a missing environment gives a clear message.
rem Add the argument "nopause" to skip the "press a key" prompt on an error (used by the tests).

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

"%PY%" -c "import streamlit, pandas, sacrebleu" >nul 2>&1
if errorlevel 1 (
    set "MSG=ERROR: Python or the required libraries were not found. Run setup_model_env.bat first."
    goto :fail
)

"%PY%" -m streamlit run app.py --server.address localhost
exit /b %errorlevel%

:fail
echo.
echo %MSG%
if /i not "%~1"=="nopause" pause
exit /b 1

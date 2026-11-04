@echo off
cd /d "%~dp0"
rem Uses the .venv made by setup_model_env.bat if it exists, otherwise the default Python.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run app.py --server.address localhost
) else (
    python -m streamlit run app.py --server.address localhost
)

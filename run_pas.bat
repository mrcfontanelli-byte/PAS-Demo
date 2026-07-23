@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtuale .venv non trovato.
    echo Crealo con: python -m venv .venv
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py
pause

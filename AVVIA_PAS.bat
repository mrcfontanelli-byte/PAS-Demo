@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtuale non trovato.
    echo Avvia prima INSTALLA_E_AVVIA.bat
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py
pause

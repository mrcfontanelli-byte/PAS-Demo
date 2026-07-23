@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo PAS Demo v2.5.11 - Installazione pulita
echo ============================================

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Creazione ambiente virtuale...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERRORE: impossibile creare .venv.
        echo Verifica che Python sia installato e disponibile nel PATH.
        pause
        exit /b 1
    )
)

echo.
echo Aggiornamento pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERRORE durante l'aggiornamento di pip.
    pause
    exit /b 1
)

echo.
echo Installazione librerie...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERRORE durante l'installazione delle librerie.
    pause
    exit /b 1
)

echo.
echo Verifica moduli PAS...
".venv\Scripts\python.exe" -c "from modules.charts import CHARTS_MODULE_VERSION, historical_boxplot, compact_reference_boxplot; assert CHARTS_MODULE_VERSION == '2.1.4'; print('VERIFICA MODULI: OK')"
if errorlevel 1 (
    echo ERRORE: verifica moduli non superata.
    pause
    exit /b 1
)

echo.
echo Avvio PAS...
".venv\Scripts\python.exe" -m streamlit run app.py

endlocal

@echo off
chcp 65001 > nul

echo European Language Detector

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found. Install Python 3.11+ and try again.
    pause
    exit /b
)

echo [INFO] Installing dependencies...
python -m pip install -r requirements.txt

if not exist data\train.jsonl (
    echo [INFO] Building starter dataset...
    python -m src.seed_dataset
    python -m src.build_dataset
)

if not exist models\profiles.json (
    echo [INFO] Training local profiles...
    python -m src.train
)

echo.
echo 1 - Console mode
echo 2 - API server
echo 3 - Evaluate and refresh report
echo 4 - Production server
set /p choice=Select mode: 

if "%choice%"=="1" (
    python run.py
) else if "%choice%"=="2" (
    python api/app.py
) else if "%choice%"=="3" (
    python -m src.evaluate
) else if "%choice%"=="4" (
    set ELD_DEBUG=0
    python serve.py
) else (
    echo Invalid choice
)

pause

@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  Brightloop Subscription Management Platform — Launcher
echo  Odoo Hackathon Kochi
echo =====================================================================

:: 1. Copy .env.example to .env if missing
if not exist ".env" (
    echo [1/4] Creating .env from .env.example...
    copy .env.example .env > nul
) else (
    echo [1/4] Existing .env detected.
)

:: 2. Setup Virtual Environment if missing
if not exist "venv\Scripts\python.exe" (
    echo [2/4] Initializing Python virtual environment in .\venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Python not found in PATH or failed to create venv.
        pause
        exit /b 1
    )
) else (
    echo [2/4] Python virtual environment ready.
)

:: 3. Install Requirements
echo [3/4] Checking and installing dependencies...
.\venv\Scripts\pip.exe install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: 4. Database initialization and seeding check
if not exist "brightloop.db" (
    echo [4/4] First boot: Initializing schema and seeding demo catalog...
    .\venv\Scripts\python.exe seed.py
) else (
    echo [4/4] Database brightloop.db detected.
)

echo.
echo =====================================================================
echo  SUCCESS: Brightloop is starting on http://localhost:8000
echo  - Web Application: http://localhost:8000
echo  - Interactive API Docs: http://localhost:8000/docs
echo.
echo  Default Demo Credentials:
echo    Administrator : admin@brightloop.com / Admin@12345
echo    Billing Staff : staff@brightloop.com / Staff@12345
echo    Customer Demo : alex@acme.com        / Customer@12345
echo =====================================================================
echo.

:: Single worker is required because SSE in-process event bus runs in-memory
.\venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1

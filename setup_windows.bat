@echo off
REM Windows Setup Script for Hire Report Automation
REM This script sets up the Python virtual environment and installs dependencies

echo ========================================
echo Setting up Hire Report Automation
echo ========================================

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo Python found. Creating virtual environment...

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install Python dependencies
echo Installing Python packages...
pip install -r requirements.txt

REM Install Playwright browsers
echo Installing Playwright browsers...
playwright install chromium

REM Deactivate virtual environment
call deactivate

echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Set environment variables in Windows:
echo    - Right-click This PC ^> Properties ^> Advanced system settings
echo    - Environment Variables ^> New (System or User variables)
echo    - HIRE_USER = your_username
echo    - HIRE_PASS = your_password
echo.
echo 2. Test the script: run_hire_report.bat
echo.
echo 3. Set up Task Scheduler for automatic runs
echo.

pause
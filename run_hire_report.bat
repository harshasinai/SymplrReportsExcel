@echo off
REM Windows Batch Script for Hire Report Download
REM Usage: run_hire_report.bat

echo ========================================
echo Hire Report Download - Windows VM
echo ========================================

REM Set working directory to script location
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup_windows.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Set environment variables (you can also set these system-wide)
if "%HIRE_USER%"=="" (
    echo ERROR: HIRE_USER environment variable not set.
    echo Set it in System Properties ^> Environment Variables
    pause
    exit /b 1
)

if "%HIRE_PASS%"=="" (
    echo ERROR: HIRE_PASS environment variable not set.
    echo Set it in System Properties ^> Environment Variables
    pause
    exit /b 1
)

REM Run the Python script
echo Starting hire report download...
python scripts\download_hire_report.py --quiet

REM Check if successful
if %ERRORLEVEL% EQU 0 (
    echo ========================================
    echo SUCCESS: Hire report downloaded!
    echo ========================================
) else (
    echo ========================================
    echo ERROR: Download failed!
    echo Check hire_report.log for details
    echo ========================================
)

REM Deactivate virtual environment
call deactivate

REM Keep window open for 10 seconds so user can see result
timeout /t 10 /nobreak > nul

exit /b %ERRORLEVEL%
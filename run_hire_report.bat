@echo off
setlocal
REM Windows Batch Script for Hire Report Download
REM Usage: run_hire_report.bat

echo ========================================
echo Hire Report Download - Windows VM
echo ========================================

REM Set working directory to script location
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found. Run setup_windows.bat first.
    exit /b 1
)

REM Required for Task Scheduler/non-interactive Windows consoles.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM Symplr credentials must be set as Windows user/system environment variables
REM for the scheduled task account.
if "%DOWNLOAD_DIR%"=="" set "DOWNLOAD_DIR=%USERPROFILE%\Downloads\Symplr"

REM Confirm required environment variables are available.
if "%HIRE_USER%"=="" (
    echo ERROR: HIRE_USER environment variable not set.
    echo Set it in System Properties ^> Environment Variables
    exit /b 1
)

if "%HIRE_PASS%"=="" (
    echo ERROR: HIRE_PASS environment variable not set.
    echo Set it in System Properties ^> Environment Variables
    exit /b 1
)

REM Run the Python script
echo Starting hire report download...
".venv\Scripts\python.exe" scripts\download_hire_report.py --quiet --headless
set "SCRIPT_EXIT=%ERRORLEVEL%"

REM Check if successful
if "%SCRIPT_EXIT%"=="0" (
    echo ========================================
    echo SUCCESS: Hire report downloaded!
    echo ========================================
) else (
    echo ========================================
    echo ERROR: Download failed!
    echo Check hire_report.log for details
    echo ========================================
    exit /b %SCRIPT_EXIT%
)

REM Optional SharePoint upload path. Set SHAREPOINT_SYNC_DIR to the local
REM OneDrive-synced SymplrEntries folder from the OnboardingProject site.
if not "%SHAREPOINT_SYNC_DIR%"=="" (
    echo Copying latest CSV to SharePoint sync folder...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $target = $env:SHAREPOINT_SYNC_DIR; if (-not (Test-Path -LiteralPath $target)) { throw 'SHAREPOINT_SYNC_DIR does not exist: ' + $target }; $latest = Get-ChildItem -LiteralPath $env:DOWNLOAD_DIR -Filter 'SymplrHireList_*.csv' | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $latest) { throw 'No SymplrHireList CSV found in ' + $env:DOWNLOAD_DIR }; Copy-Item -LiteralPath $latest.FullName -Destination $target -Force; Write-Host ('Copied to SharePoint sync folder: ' + (Join-Path $target $latest.Name))"
    if errorlevel 1 (
        echo ERROR: SharePoint sync copy failed.
        exit /b 1
    )
) else (
    echo SharePoint upload skipped. Set SHAREPOINT_SYNC_DIR to the local synced SymplrEntries folder.
)

REM Optional success email. Configure SUCCESS_EMAIL_TO plus SMTP_* variables.
if not "%SUCCESS_EMAIL_TO%"=="" (
    echo Sending success notification email...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\send_success_email.ps1"
    if errorlevel 1 (
        echo ERROR: Success email failed.
        exit /b 1
    )
) else (
    echo Success email skipped. Set SUCCESS_EMAIL_TO to enable notifications.
)

exit /b 0

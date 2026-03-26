# Setup Guide for New Machine (macOS or Windows)

This guide walks you through setting up the Hires Report automation script on a fresh machine.

# This is the main overview to install everything needed and run the this project on a new machine
# Key Downloads for New Machine:

1. Python 3.7+ - python.org

2. Project files - Copy from original machine:

        download_hire_report.py
        requirements.txt
        README.md
        AUTOMATION_SETUP.md
        SETUP_NEW_MACHINE.md
3. Everything else - Installs automatically via "pip install -r requirements.txt"



## Prerequisites

Before starting, ensure you have:
- **Python 3.7+** installed ([Download Python](https://www.python.org/downloads/))
- **Git** installed (optional, for cloning the project)
- **Terminal/PowerShell** access
- **Internet connection** (to download dependencies)

## Step 1: Copy or Download the Project

### Option A: Copy from existing machine
If you already have the project on another machine, copy the entire `myapp` folder:

**macOS/Linux:**
```bash
# On source machine, create a zip file
cd ~/Documents
zip -r myapp.zip myapp/

# Transfer myapp.zip to new machine, then unzip
unzip myapp.zip
cd myapp
```

**Windows PowerShell:**
```powershell
# On source machine
cd Documents
Compress-Archive -Path myapp -DestinationPath myapp.zip

# Transfer myapp.zip to new machine, then right-click > Extract All
# Or use PowerShell:
Expand-Archive -Path myapp.zip -DestinationPath .
cd myapp
```

### Option B: Manual Setup from Scratch
Create the project structure manually:

**macOS/Linux:**
```bash
mkdir -p ~/Documents/myapp/scripts
mkdir -p ~/Documents/myapp/logs
mkdir -p ~/Documents/myapp/downloads
cd ~/Documents/myapp
```

**Windows PowerShell:**
```powershell
mkdir C:\Users\YourUsername\Documents\myapp\scripts
mkdir C:\Users\YourUsername\Documents\myapp\logs
mkdir C:\Users\YourUsername\Documents\myapp\downloads
cd C:\Users\YourUsername\Documents\myapp
```

Then copy these files from the original machine:
- `scripts/download_hire_report.py`
- `requirements.txt`
- `.hire_report_env.sample`
- `README.md`
- `AUTOMATION_SETUP.md`

## Step 2: Create Environment Configuration File

### macOS/Linux:
```bash
# Create the file in your home directory
cat > ~/.hire_report_env << EOF
HIRE_URL=https://pm.healthcaresource.com/PM/sinai/Account/LogOn
HIRE_USER=your_username_here
HIRE_PASS=your_password_here
DOWNLOAD_DIR=/Users/YourUsername/Documents/myapp/downloads
HEADLESS=1
EOF
```

Replace:
- `your_username_here` with your actual login username
- `your_password_here` with your actual login password
- `/Users/YourUsername` with your actual macOS username

### Windows PowerShell:
```powershell
# Create the file in your home directory
$content = @"
HIRE_URL=https://pm.healthcaresource.com/PM/sinai/Account/LogOn
HIRE_USER=your_username_here
HIRE_PASS=your_password_here
DOWNLOAD_DIR=C:\Users\YourUsername\Documents\myapp\downloads
HEADLESS=1
"@

$content | Set-Content -Path "$env:USERPROFILE\.hire_report_env"
```

Replace:
- `your_username_here` with your actual login username
- `your_password_here` with your actual login password
- `YourUsername` with your actual Windows username

## Step 3: Install Python Virtual Environment

### macOS/Linux:
```bash
cd ~/Documents/myapp

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# You should see (.venv) at the start of your terminal prompt
```

### Windows PowerShell:
```powershell
cd C:\Users\YourUsername\Documents\myapp

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# You should see (.venv) at the start of your PowerShell prompt
```

### Windows Command Prompt:
```cmd
cd C:\Users\YourUsername\Documents\myapp
python -m venv .venv
.venv\Scripts\activate.bat
```

## Step 4: Install Required Dependencies

With virtual environment activated, run:

### macOS/Linux:
```bash
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
```

### Windows (PowerShell or Command Prompt):
```powershell
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
```

**What gets installed:**
- `playwright` - Browser automation library
- `python-dotenv` - Environment variable management
- Chromium browser (via playwright install)

## Step 5: Test the Script

### macOS/Linux:
```bash
cd ~/Documents/myapp
source .venv/bin/activate
python scripts/download_hire_report.py
```

### Windows PowerShell:
```powershell
cd C:\Users\YourUsername\Documents\myapp
.venv\Scripts\activate
python scripts/download_hire_report.py
```

**Expected output:**
```
Start date: 12/03/2025
Opening login page...
Logging in...
✓ Login successful
✓ Export menu opened
✓ Export Report dialog opened
Selecting CSV format...
Waiting for download to complete...
✓ CSV saved to: /Users/YourUsername/Documents/myapp/downloads/hire_report_20251205_120000.csv
```

If successful, verify the CSV was created:

### macOS/Linux:
```bash
ls -lh ~/Documents/myapp/downloads/
```

### Windows PowerShell:
```powershell
ls C:\Users\YourUsername\Documents\myapp\downloads\
```

## Step 6: Set Up Automated Daily Schedule

### macOS (LaunchAgent):

```bash
launchctl load ~/Library/LaunchAgents/com.hire.report.downloader.plist
```

The plist file should already exist if you copied the project. If not, create it manually (see `AUTOMATION_SETUP.md`).

Verify it's loaded:
```bash
launchctl list | grep hire
```

### Windows (Task Scheduler):

1. Open **Task Scheduler**
2. Click **Create Basic Task** → Name: `Hire Report Download`
3. **Trigger** tab: Select "Daily" at 9:00 PM
4. **Action** tab:
   - **Program**: `C:\Users\YourUsername\Documents\myapp\.venv\Scripts\python.exe`
   - **Arguments**: `C:\Users\YourUsername\Documents\myapp\scripts\download_hire_report.py`
   - **Start in**: `C:\Users\YourUsername\Documents\myapp`
5. Click **Finish**

Verify it's created:
- Task Scheduler → Task Scheduler Library → Find "Hire Report Download"

## Step 7: Verify Everything Works

### Check if automated scheduler is running:

**macOS:**
```bash
# View automation logs
tail -f ~/Documents/myapp/logs/hire_report.log

# Check scheduler status
launchctl list | grep hire
```

**Windows:**
- Open Task Scheduler → Find "Hire Report Download" task
- Right-click → View All Properties → Verify schedule

### Manual test anytime:

**macOS/Linux:**
```bash
cd ~/Documents/myapp && source .venv/bin/activate && python scripts/download_hire_report.py
```

**Windows PowerShell:**
```powershell
cd C:\Users\YourUsername\Documents\myapp && .venv\Scripts\activate && python scripts/download_hire_report.py
```

## What to Download/Install Manually

If setting up from scratch, you need to download:

1. **Python** (3.7 or higher)
   - [python.org](https://www.python.org/downloads/)
   - Choose "Add Python to PATH" during installation

2. **Project Files** (from original machine)
   - `scripts/download_hire_report.py`
   - `requirements.txt`
   - `README.md`
   - `AUTOMATION_SETUP.md`
   - `.hire_report_env.sample`

3. **Everything else installs via pip:**
   - Playwright (browser automation)
   - Python-dotenv (environment variables)
   - Chromium browser (via `python -m playwright install`)

## Directory Structure

After setup, your project should look like:

```
myapp/
├── scripts/
│   └── download_hire_report.py
├── logs/
│   └── hire_report_cron.log (created after first run)
├── downloads/
│   └── hire_report_20251205_*.csv (created after each run)
├── .venv/
│   ├── bin/ (macOS/Linux) or Scripts/ (Windows)
│   └── lib/
├── requirements.txt
├── README.md
├── AUTOMATION_SETUP.md
└── .hire_report_env.sample
```

## Troubleshooting

### "Command not found: python3" (macOS/Linux)
```bash
# Use python instead
python -m venv .venv
```

### "ModuleNotFoundError: No module named 'playwright'"
Make sure virtual environment is activated:
```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### Script can't find credentials
Verify `.hire_report_env` file exists:
```bash
# macOS/Linux
cat ~/.hire_report_env

# Windows PowerShell
cat $env:USERPROFILE\.hire_report_env
```

### Download folder not found
Create it manually:
```bash
# macOS/Linux
mkdir -p ~/Documents/myapp/downloads

# Windows PowerShell
mkdir -Path C:\Users\YourUsername\Documents\myapp\downloads
```

## Summary

**Total time to setup:** ~10-15 minutes

**Key commands to remember:**
- **Activate venv**: `source .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate` (Windows)
- **Run manually**: `python scripts/download_hire_report.py`
- **Check logs**: `tail -f ~/Documents/myapp/logs/hire_report.log` (macOS/Linux)

Once set up, the script runs automatically every day at 9:00 PM. No further action needed!

For detailed automation help, see `AUTOMATION_SETUP.md`.

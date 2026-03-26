# Hires Report Automation

This project contains a Playwright script to automatically download the "Hires Report" CSV from your application.

Files added:
- `scripts/download_hire_report.py` - main automation script
- `requirements.txt` - Python dependencies
- `.hire_report_env.sample` - sample environment variables

Quick setup

1. Create a Python venv and install deps:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
```

2. Copy env sample to your home and edit credentials:
```bash
cp .hire_report_env.sample ~/.hire_report_env
# edit ~/.hire_report_env and set HIRE_USER and HIRE_PASS
```

3. Run the script manually to test:
```bash
source .venv/bin/activate
python scripts/download_hire_report.py
```

## Run Manually On-The-Fly

If you need to download the report right now (any time of day), use this command:

### Quick One-Line Command
```bash
cd /Users/Harsha/Documents/myapp && source .venv/bin/activate && python scripts/download_hire_report.py
```

### Or Step-by-Step
```bash
# Navigate to project folder
cd /Users/Harsha/Documents/myapp

# Activate virtual environment
source .venv/bin/activate

# Run the script
python scripts/download_hire_report.py
```

**What to expect:**
- You'll see messages like `✓ Login successful`, `✓ Export Report dialog opened`, etc.
- When you see `✓ CSV saved to: /Users/Harsha/Documents/myapp/downloads/hire_report_YYYYMMDD_HHMMSS.csv` - the download is complete!
- The CSV file is ready in the downloads folder

**Verify the download:**
```bash
ls -lh /Users/Harsha/Documents/myapp/downloads/ | tail -3
```

## Automated Daily Schedule

The script runs automatically every day at **9:00 PM** via macOS LaunchAgent. No manual intervention needed!

To check the automated execution:
```bash
# View the logs from automatic runs
tail -f /Users/Harsha/Documents/myapp/logs/hire_report.log

# Check if scheduler is active
launchctl list | grep hire
```

To disable automatic scheduling:
```bash
launchctl unload /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
```

To re-enable automatic scheduling:
```bash
launchctl load /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
```

See `AUTOMATION_SETUP.md` for detailed automation instructions.

## Troubleshooting

Notes
- The script includes fallback selector attempts but you should verify selectors with your browser inspector and update selectors in `download_hire_report.py` if clicks/fills fail.
- If your site uses SSO or an identity provider, adjust the login sequence accordingly.
- For debugging set `HEADLESS=0` in `~/.hire_report_env` and run the script interactively.
- If the script fails to run, check the logs: `tail -50 /Users/Harsha/Documents/myapp/logs/hire_report.log`
- Verify credentials are set in `~/.hire_report_env`: `cat ~/.hire_report_env`

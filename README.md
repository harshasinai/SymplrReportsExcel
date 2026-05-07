# Hire Report Automation - Windows VM

This project automates downloading hire reports from Symplr Recruiting using Playwright and runs on a Windows VM with Task Scheduler.

## Features
- ✅ Automated login to Symplr Recruiting
- ✅ Downloads UAFCompare1 reports as CSV
- ✅ Runs on schedule via Windows Task Scheduler
- ✅ Includes retry logic and error handling
- ✅ Generates debug screenshots on failures
- ✅ **Cost: FREE** (uses your existing Windows VM)

## Quick Start (Windows VM)

### 1. Initial Setup
```cmd
# Copy project to Windows VM (e.g., C:\hire-report-automation\)
# Open Command Prompt as Administrator
cd C:\hire-report-automation
setup_windows.bat
```

### 2. Configure Credentials
Set environment variables in Windows:
- Right-click **This PC** → **Properties** → **Advanced system settings**
- **Environment Variables** → **New** (System variables)
- `HIRE_USER` = `sa-powerapps`
- `HIRE_PASS` = `passwd`

### 3. Test Manually
```cmd
run_hire_report.bat
```

### 4. Set Up Daily Automation
- Open Task Scheduler (`taskschd.msc`)
- Create new task → Point to `C:\hire-report-automation\run_hire_report.bat`
- Schedule for daily execution (e.g., 6:00 AM)

## File Structure
```
C:\hire-report-automation\
├── scripts\
│   └── download_hire_report.py    # Main automation script
├── downloads\                     # CSV output folder
├── logs\                          # Log files
├── run_hire_report.bat            # Windows batch runner
├── setup_windows.bat              # Initial setup script
├── requirements.txt               # Python dependencies
├── WINDOWS_SETUP.md               # Detailed setup guide
└── hire_report.log                # Execution logs
```

## Manual Testing

### Run Immediately (Any Time)
```cmd
cd C:\hire-report-automation
run_hire_report.bat
```

### Check Results
- CSV files: `downloads\` folder
- Logs: `hire_report.log`
- Screenshots: `downloads\screenshots\` (on errors)

## Troubleshooting

### Script Won't Run
- Check `hire_report.log` for error messages
- Verify environment variables are set
- Test: `python scripts\download_hire_report.py` directly

### Task Scheduler Issues
- Right-click task → **Run** to test manually
- Check **History** tab for execution details
- Verify **Run with highest privileges** is enabled

### Browser Issues
- Reinstall browsers: `playwright install chromium`
- Check internet connectivity

## Maintenance
- Monitor disk space (CSV files accumulate)
- Review logs weekly
- Update dependencies quarterly

## Security
- Credentials stored in Windows environment variables
- Task runs with administrator privileges
- Keep VM updated with security patches

---

**Detailed Setup**: See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for step-by-step instructions.
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

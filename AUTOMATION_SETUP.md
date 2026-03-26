# Automated Hires Report Download - Setup Complete ✓

## Current Status
The script is now **fully automated** and will run every day at **9:00 PM (21:00)**.

## How It Works

### macOS Automation (LaunchAgent)
- **Scheduler**: macOS LaunchAgent (similar to cron but more reliable)
- **Frequency**: Daily at 9:00 PM
- **Command**: Automatically runs the Python script from the project folder
- **Logs**: Saved to `/Users/Harsha/Documents/myapp/logs/hire_report.log`

### What Happens Each Day at 9 PM
1. LaunchAgent wakes up
2. Runs the Python script using the virtual environment
3. Script logs into HealthCareSource portal
4. Navigates to Hires Report
5. Exports data as CSV
6. Saves to: `/Users/Harsha/Documents/myapp/downloads/hire_report_YYYYMMDD_HHMMSS.csv`
7. Logs all activity to the log file

## Files Created/Modified

### LaunchAgent Configuration
```
/Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
```

### Log Files (created automatically)
```
/Users/Harsha/Documents/myapp/logs/hire_report.log          (standard output)
/Users/Harsha/Documents/myapp/logs/hire_report_error.log    (errors)
```

### Downloaded CSVs
```
/Users/Harsha/Documents/myapp/downloads/hire_report_*.csv
```

## How to Run Manually On-The-Fly

If you need to download the report right now (any time of day), use one of these methods:

### Method 1: Quick One-Line Command (Recommended)
Open Terminal and paste this entire command:
```bash
cd /Users/Harsha/Documents/myapp && source .venv/bin/activate && python scripts/download_hire_report.py
```

### Method 2: Step-by-Step (if you prefer)
Open Terminal and run these commands one by one:

**Step 1:** Navigate to the project folder
```bash
cd /Users/Harsha/Documents/myapp
```

**Step 2:** Activate the virtual environment
```bash
source .venv/bin/activate
```
You should see `(.venv)` at the beginning of your terminal prompt.

**Step 3:** Run the script
```bash
python scripts/download_hire_report.py
```

### Expected Output
You'll see messages like:
```
Start date: 12/03/2025
Opening login page...
Logging in...
✓ Login successful
...
✓ CSV saved to: /Users/Harsha/Documents/myapp/downloads/hire_report_20251205_120000.csv
```

When you see the last line with the file path, the download is complete! ✓

### After Manual Run
Check that the CSV was created:
```bash
ls -lh /Users/Harsha/Documents/myapp/downloads/ | tail -3
```

## Useful Commands

### Check if automated scheduling is active
```bash
launchctl list | grep hire
```

### View automation logs (real-time)
```bash
tail -f /Users/Harsha/Documents/myapp/logs/hire_report.log
```

### View recent downloads
```bash
ls -lh /Users/Harsha/Documents/myapp/downloads/hire_report_*.csv | tail -5
```

### View the content of latest downloaded CSV
```bash
head -5 /Users/Harsha/Documents/myapp/downloads/hire_report_*.csv | tail -2
```

### Disable automatic scheduling
```bash
launchctl unload /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
```

### Re-enable automatic scheduling
```bash
launchctl load /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
```

### Uninstall completely
```bash
launchctl unload /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
rm /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
```

## Troubleshooting

### Script not running?
1. Check if LaunchAgent is loaded: `launchctl list | grep hire`
2. Check logs: `tail -50 /Users/Harsha/Documents/myapp/logs/hire_report.log`
3. Verify environment file exists: `cat ~/.hire_report_env`
4. Test manually: `cd /Users/Harsha/Documents/myapp && source .venv/bin/activate && python scripts/download_hire_report.py`

### Logs not showing anything?
The script may not be running yet. First execution will be at 9:00 PM today.
Check back tomorrow after 9 PM.

### Need to change the time?
Edit `/Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist` and change the `<integer>21</integer>` (21 = 9 PM, use 0-23 format):
- 2 AM = 2
- 6 AM = 6
- 2 PM = 14
- 9 PM = 21

Then reload:
```bash
launchctl unload /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
launchctl load /Users/Harsha/Library/LaunchAgents/com.hire.report.downloader.plist
```

## Important Notes
- ✓ Script is cross-platform compatible (works on Windows too with Task Scheduler)
- ✓ Credentials are stored safely in `~/.hire_report_env` (not in the script)
- ✓ Each run creates a new timestamped CSV file
- ✓ No manual intervention needed - completely automated!
- ✓ Will continue running indefinitely unless disabled

## Next Steps
1. The script will run automatically at 9:00 PM today
2. Check the logs tomorrow: `tail /Users/Harsha/Documents/myapp/logs/hire_report.log`
3. Verify the CSV was downloaded: `ls -lh /Users/Harsha/Documents/myapp/downloads/`

All set! Your daily automated Hires Report download is now active. 🎉

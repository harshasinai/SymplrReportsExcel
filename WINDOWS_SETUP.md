# Windows VM Setup Guide - Hire Report Automation

## Overview
This guide helps you set up automated daily hire report downloads on a Windows VM using Task Scheduler.

## Prerequisites
- Windows 10/11 VM
- Python 3.9+ installed
- Administrator access to set up Task Scheduler

---

## Step 1: Initial Setup

### 1.1 Copy Project to Windows VM
Copy the entire project folder to your Windows VM (e.g., `C:\hire-report-automation\`)

### 1.2 Run Setup Script
1. Open Command Prompt as Administrator
2. Navigate to project folder:
   ```cmd
   cd C:\hire-report-automation
   ```
3. Run the setup script:
   ```cmd
   setup_windows.bat
   ```

This will:
- Create Python virtual environment
- Install required packages
- Install Playwright browsers

---

## Step 2: Configure Environment Variables

### Option A: System Environment Variables (Recommended)
1. Right-click **This PC** → **Properties**
2. Click **Advanced system settings**
3. Click **Environment Variables**
4. Under **System variables** (or **User variables**), click **New**
5. Add these variables:

| Variable Name | Value |
|---|---|
| `HIRE_USER` | `sa-powerapps` |
| `HIRE_PASS` | `Digital1500` |
| `DOWNLOAD_DIR` | `C:\hire-report-automation\downloads` (optional) |

### Option B: Set in Batch File
Edit `run_hire_report.bat` and uncomment/modify these lines:
```batch
REM Set credentials (uncomment and modify)
REM set HIRE_USER=sa-powerapps
REM set HIRE_PASS=Digital1500
```

---

## Step 3: Test the Script

### Manual Test
1. Open Command Prompt
2. Navigate to project folder
3. Run: `run_hire_report.bat`
4. Verify CSV downloads to `C:\hire-report-automation\downloads\`

### Expected Output
```
=======================================
Hire Report Download - Windows VM
=======================================
Starting hire report download...
✅  Download complete!
    File : C:\hire-report-automation\downloads\Current_Layout-CSV_20260506_153522.csv
=======================================
SUCCESS: Hire report downloaded!
=======================================
```

---

## Step 4: Set Up Task Scheduler

### 4.1 Open Task Scheduler
1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Click **Create Task** (right panel)

### 4.2 General Tab
- **Name**: `Hire Report Download`
- **Description**: `Daily automated download of hire reports from Symplr`
- ✅ **Run with highest privileges**
- ✅ **Run whether user is logged on or not**
- **Configure for**: `Windows 10` (or your Windows version)

### 4.3 Triggers Tab
1. Click **New**
2. **Begin the task**: `On a schedule`
3. **Settings**:
   - Daily
   - Start: `6:00 AM` (or your preferred time)
   - ✅ **Repeat task every**: `1 days`
4. ✅ **Enabled**
5. Click **OK**

### 4.4 Actions Tab
1. Click **New**
2. **Action**: `Start a program`
3. **Program/script**: `C:\hire-report-automation\run_hire_report.bat`
4. **Start in**: `C:\hire-report-automation\`
5. Click **OK**

### 4.5 Conditions Tab
- ✅ **Start the task only if the computer is on AC power**
- ✅ **Wake the computer to run this task**
- ✅ **Start only if the following network connection is available**: `Any connection`

### 4.6 Settings Tab
- ✅ **Allow task to be run on demand**
- ✅ **Run task as soon as possible after a scheduled start is missed**
- ✅ **If the task fails, restart every**: `5 minutes`, **Attempt to restart up to**: `3 times`
- ✅ **Stop the task if it runs longer than**: `1 hour`
- ✅ **If the running task does not end when requested, force it to stop**

### 4.7 Save and Test
1. Click **OK**
2. Enter administrator password when prompted
3. Right-click the task → **Run**
4. Check if it completes successfully

---

## Step 5: Monitor and Troubleshoot

### View Task History
1. Right-click task → **Properties**
2. **History** tab → View execution logs

### Check Logs
- Main log: `hire_report.log`
- Screenshots: `downloads\screenshots\` (if errors occur)

### Common Issues

#### Task doesn't run
- Check **Task Scheduler** → **Task Status** shows "Ready"
- Verify **Run with highest privileges** is checked
- Test by running manually: right-click task → **Run**

#### Script fails
- Check `hire_report.log` for error messages
- Verify environment variables are set correctly
- Test batch file manually: `run_hire_report.bat`

#### Browser issues
- Playwright browsers might need reinstall: `playwright install chromium`
- Check if VM has internet access

---

## Step 6: Backup and Maintenance

### Regular Maintenance
- Monitor disk space (CSV files accumulate)
- Review logs weekly for errors
- Update Python packages quarterly: `pip install -r requirements.txt --upgrade`

### Backup Strategy
- Schedule regular backups of the `downloads\` folder
- Keep multiple months of CSV files for historical reference

### Update Credentials
When passwords change:
1. Update environment variables
2. Test script manually
3. Verify Task Scheduler still works

---

## File Structure (After Setup)
```
C:\hire-report-automation\
├── .venv\                    # Python virtual environment
├── scripts\
│   └── download_hire_report.py  # Main script
├── downloads\                # CSV output folder
│   └── screenshots\          # Debug screenshots
├── logs\                     # Log files
├── run_hire_report.bat       # Batch runner
├── setup_windows.bat         # Setup script
├── requirements.txt          # Python dependencies
├── hire_report.log           # Main log file
└── README.md                 # This documentation
```

---

## Cost
- **Free** - Uses your existing Windows VM
- Only requires electricity to run the VM

---

## Security Notes
- Store credentials in System Environment Variables (not in files)
- Run Task Scheduler as administrator
- Keep VM updated with Windows security patches
- Consider encrypting sensitive data if VM is shared

---

## Support
If issues occur:
1. Check `hire_report.log` for error details
2. Run script manually to reproduce issue
3. Verify network connectivity to Symplr
4. Check Task Scheduler event logs

The script includes automatic retries and detailed logging to help diagnose issues.
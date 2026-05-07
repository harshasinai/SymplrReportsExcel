# Script Improvements (April 26, 2026)

## What's New

### 1. **CSV File Validation** ✅
- Automatically validates downloaded CSV after each run
- Checks: file existence, minimum size (100 bytes), readability, column delimiters
- Prevents incomplete or corrupted downloads from being accepted
- Logged: `✅ CSV validation passed (9457 bytes)`

### 2. **Main-Level Retry Logic** ✅
- Full automation can retry automatically (default: 3 attempts)
- Uses **exponential backoff**: 5s → 10s → 20s between retries
- Graceful degradation: if a run fails, tries again instead of immediately exiting
- Logged: `Attempt 1/3`, `✅ Success on attempt 1`

### 3. **Configurable Timeouts** ✅
- Extracted magic numbers to named constants (easier to tune):
  - `LONG_TIMEOUT = 90_000ms` (reports loading, downloads)
  - `NETWORK_TIMEOUT = 30_000ms` (page navigation)
  - `MODAL_TIMEOUT = 5_000ms` (email dialogs)
  - `SHORT_TIMEOUT = 15_000ms` (general UI)
  - `MIN_CSV_BYTES = 100` (file validation)

### 4. **Quiet Mode for Scheduled Runs** ✅
- New flag: `--quiet` suppresses logging output
- Usage: `python script.py --quiet` for cron jobs
- File path still printed even in quiet mode for verification
- Example: `0 0 * * 0 source ~/.hire_report_env && python ~/script.py --quiet >> ~/cron.log 2>&1`

### 5. **Enhanced Logging** ✅
- Detailed audit trail in `hire_report.log`
- Logged events:
  - Retry attempts with timing
  - CSV validation results with file size
  - Success confirmation with attempt number
  - Error messages and recovery attempts

## How to Use

### Normal Run (with visual feedback)
```bash
python scripts/download_hire_report.py
```

### With Custom Dates
```bash
python scripts/download_hire_report.py --start 05/11/2026 --end 05/11/2026
```

### Scheduled/Cron (minimal output)
```bash
python scripts/download_hire_report.py --quiet
```

### Headless + Quiet (for background execution)
```bash
python scripts/download_hire_report.py --headless --quiet
```

## What Didn't Change
- ✅ All 9 automation steps work identically
- ✅ Date filtering and validation
- ✅ View Report clicking mechanism
- ✅ CSV export and download
- ✅ Screenshots at each step
- ✅ Error handling with emergency screenshots
- ✅ Credential handling via environment variables

## Safety Features
1. **Automatic recovery** - Retries 3 times with increasing delays
2. **File validation** - Confirms CSV is real before considering success
3. **Graceful timeout handling** - Uses 1.2x buffer on network timeouts
4. **Mock-resilient** - Works across different network speeds
5. **Audit trail** - Every run logged to `hire_report.log`

## Example Logs
```
2026-04-26 12:27:06,245 - INFO - Attempt 1/3
2026-04-26 12:28:39,089 - INFO - ✅ CSV validation passed (9457 bytes)
2026-04-26 12:28:42,371 - INFO - ✅ Success on attempt 1
```

## Configuration
Edit these constants at the top of `download_hire_report.py`:
```python
MAX_RETRIES = 3                    # Number of retry attempts
RETRY_DELAY = 5                    # Initial retry delay (seconds)
TIMEOUT_BUFFER = 1.2               # 20% extra on timeouts
MIN_CSV_BYTES = 100                # Minimum CSV file size
```

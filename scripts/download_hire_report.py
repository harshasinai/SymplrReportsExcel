#!/usr/bin/env python3
"""Automate Hires Report CSV download from HealthCareSource portal - Cross-platform."""

import os
import sys
import time
import shutil
import platform
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

# Load environment
env_path = Path.home() / '.hire_report_env'
if env_path.exists():
    load_dotenv(env_path)

HIRE_URL = os.getenv('HIRE_URL')
HIRE_USER = os.getenv('HIRE_USER')
HIRE_PASS = os.getenv('HIRE_PASS')
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', str(ROOT / 'downloads'))


def run():
    if not HIRE_URL or not HIRE_USER or not HIRE_PASS:
        print('Missing required env vars in ~/.hire_report_env')
        sys.exit(2)

    start_date = (datetime.now() - timedelta(days=2)).strftime('%m/%d/%Y')
    print(f'Start date: {start_date}')

    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_filename = f'hire_report_{timestamp}.csv'
    out_path = os.path.join(DOWNLOAD_DIR, out_filename)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Configure downloads to go to our project folder
        context = browser.new_context(
            accept_downloads=True,
            extra_http_headers={}
        )
        page = context.new_page()

        try:
            print('Opening login page...')
            page.goto(HIRE_URL, timeout=60000)
            page.wait_for_load_state('networkidle', timeout=30000)

            # Login
            print('Logging in...')
            page.fill('input[type="text"]', HIRE_USER)
            page.fill('input[type="password"]', HIRE_PASS)
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=30000)
            print('✓ Login successful')

            # Navigate to Hires Report
            print('Navigating to Hires Report...')
            time.sleep(2)  # Extra wait after login
            
            try:
                page.click('text=Insights', timeout=3000)
                page.wait_for_load_state('networkidle', timeout=15000)
            except Exception as e:
                print(f'⚠ Insights click failed: {e}')
            
            try:
                page.click('text=Reports', timeout=3000)
                page.wait_for_load_state('networkidle', timeout=15000)
            except Exception as e:
                print(f'⚠ Reports click failed: {e}')
            
            try:
                page.click('text=Hires Report', timeout=3000)
                page.wait_for_load_state('networkidle', timeout=15000)
            except Exception as e:
                print(f'⚠ Hires Report click failed: {e}')
            
            print('✓ On Hires Report page')

            # Wait a bit for page to fully settle
            time.sleep(2)

            # Set Start Date
            print(f'Setting start date to {start_date}...')
            try:
                page.click('.DayPickerInput', timeout=2000)
                time.sleep(0.3)
                page.fill('.DayPickerInput input', start_date)
                time.sleep(0.3)
                page.keyboard.press('Escape')
                time.sleep(0.5)
                print('✓ Start date set')
            except Exception as e:
                print(f'⚠ Could not set start date: {e}')
                # Continue anyway, report may already be loaded

            # View Report
            print('Clicking View Report...')
            try:
                page.click('button:has-text("View Report")', timeout=2000)
                page.wait_for_selector('table', timeout=30000)
                print('✓ Report loaded')
            except Exception as e:
                print(f'⚠ View Report button not found: {e}')
                # Continue anyway

            # Click Export icon
            print('Opening Export menu...')
            try:
                # Try standard Playwright selector first
                page.click('.ab-Icon.ab-Icon--export-data', timeout=2000)
                time.sleep(0.5)
            except:
                # Fallback to JavaScript
                try:
                    page.evaluate("""
                        const el = document.querySelector('.ab-Icon.ab-Icon--export-data');
                        if (el) {
                            const btn = el.closest('button') || el;
                            btn.click();
                        }
                    """)
                    time.sleep(0.5)
                except Exception as e:
                    print(f'✗ Export menu failed: {e}')
                    sys.exit(1)
            
            print('✓ Export menu opened')

            # Click Export Report button
            print('Clicking Export Report...')
            try:
                page.evaluate("""
                    const el = document.querySelector('.ab-Icon.ab-Icon--export');
                    if (el) {
                        const btn = el.closest('button') || el;
                        btn.click();
                    }
                """)
                time.sleep(1)
                print('✓ Export Report dialog opened')
            except Exception as e:
                print(f'✗ Export Report failed: {e}')
                sys.exit(1)

            # Click CSV option using simple JavaScript
            print('Selecting CSV format...')
            time.sleep(2)
            
            # Just click the CSV option - let browser handle download to system Downloads folder
            try:
                page.evaluate("""
                    const elements = document.querySelectorAll('*');
                    for (let el of elements) {
                        if (el.textContent && el.textContent.trim() === 'CSV') {
                            el.click();
                            break;
                        }
                    }
                """)
                
                # Wait for download to complete (check for file in Downloads)
                print('Waiting for download to complete...')
                time.sleep(3)  # Give browser time to download
                
                # Check system Downloads folder for the file
                downloads_dir = Path.home() / 'Downloads'
                hires_files = sorted(downloads_dir.glob('Hires_Report_*.csv'), key=lambda x: x.stat().st_mtime, reverse=True)
                
                if hires_files:
                    latest_file = hires_files[0]
                    # Copy to our project downloads folder
                    shutil.copy2(latest_file, out_path)
                    print(f'✓ CSV saved to: {out_path}')
                else:
                    print('✗ No CSV file found in system Downloads')
                    sys.exit(1)
                    
            except Exception as e:
                print(f'✗ CSV download failed: {e}')
                sys.exit(1)

        except Exception as e:
            print(f'✗ Fatal error: {e}')
            sys.exit(1)
        finally:
            try:
                context.close()
            except:
                pass
            browser.close()


if __name__ == '__main__':
    run()

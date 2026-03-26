#!/usr/bin/env python3
"""Debug script to check page state."""

import os
import sys
import time
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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    try:
        page.goto(HIRE_URL, timeout=60000)
        time.sleep(1)
        
        # Login
        page.fill('input[type="text"]', HIRE_USER)
        page.fill('input[type="password"]', HIRE_PASS)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle', timeout=30000)
        print('✓ Logged in')
        
        # Try to navigate
        try:
            page.click('text=Insights', timeout=3000)
            print('✓ Clicked Insights')
        except:
            print('✗ Insights not found')
        
        page.wait_for_load_state('networkidle', timeout=10000)
        
        try:
            page.click('text=Reports', timeout=3000)
            print('✓ Clicked Reports')
        except:
            print('✗ Reports not found')
            
        page.wait_for_load_state('networkidle', timeout=10000)
        
        try:
            page.click('text=Hires Report', timeout=3000)
            print('✓ Clicked Hires Report')
        except:
            print('✗ Hires Report not found')
        
        page.wait_for_load_state('networkidle', timeout=10000)
        
        # Check what elements exist
        print('\n=== PAGE ELEMENTS ===')
        has_day_picker = page.query_selector('.DayPickerInput') is not None
        print(f'DayPickerInput exists: {has_day_picker}')
        
        has_view_report = page.query_selector('button:has-text("View Report")') is not None
        print(f'View Report button exists: {has_view_report}')
        
        has_export = page.query_selector('.ab-Icon.ab-Icon--export-data') is not None
        print(f'Export icon exists: {has_export}')
        
        # Take screenshot
        screenshot_path = ROOT / 'debug_page.png'
        page.screenshot(path=screenshot_path, full_page=False)
        print(f'\nScreenshot saved to: {screenshot_path}')
        
        # Get page URL
        print(f'Current URL: {page.url}')
        
        time.sleep(5)
        
    except Exception as e:
        print(f'Error: {e}')
    finally:
        browser.close()

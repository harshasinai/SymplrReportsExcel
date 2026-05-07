#!/usr/bin/env python3
"""
symplr_uaf_download.py
──────────────────────
Automates login → UAFCompare1 report → CSV download from
Symplr Recruiting (HealthcareSource) for Sinai Chicago.

Usage
-----
  # set credentials once
  export HIRE_USER="sa-powerapps"
  export HIRE_PASS="Digital1500"
  export DOWNLOAD_DIR="~/Downloads/Symplr"   # optional

  # run (auto-calculates next bi-weekly date from anchor 2026-04-27)
  python symplr_uaf_download.py

  # explicit dates
  python symplr_uaf_download.py --start 2026-05-11 --end 2026-05-11

  # headless
  python symplr_uaf_download.py --headless

Dependencies
------------
  pip install playwright
  playwright install chromium
"""

import argparse
import os
import sys
import datetime
import logging
import time
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hire_report.log', mode='a'),  # Explicitly set append mode
        logging.StreamHandler(sys.stdout)
    ]
)

# ---------------------------------------------------------------------------
# Playwright import guard
# ---------------------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("playwright not installed. Run: pip install playwright && playwright install chromium")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOGIN_URL   = "https://pm.healthcaresource.com/PM/sinai/Account/LogOn"
REPORTS_URL = "https://pm.healthcaresource.com/PM/sinai/PMWeb/ManageReports?isMenuNavigation=true"

BI_WEEKLY_ANCHOR = datetime.date(2026, 4, 13)   # First known valid cycle date
BI_WEEKLY_DAYS   = 14

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
TIMEOUT_BUFFER = 1.2  # 20% buffer on timeouts

# Timeout values (in milliseconds)
LONG_TIMEOUT = 90_000
SHORT_TIMEOUT = 15_000
MODAL_TIMEOUT = 5_000
NETWORK_TIMEOUT = 30_000

# File validation
MIN_CSV_BYTES = 100  # Minimum reasonable CSV size


# ---------------------------------------------------------------------------
# CSV file validation
# ---------------------------------------------------------------------------
def validate_csv_file(filepath: Path) -> bool:
    """Verify that the CSV file exists and has valid content."""
    if not filepath.exists():
        logging.warning(f"CSV file does not exist: {filepath}")
        return False
    
    file_size = filepath.stat().st_size
    if file_size < MIN_CSV_BYTES:
        logging.warning(f"CSV file too small ({file_size} bytes): {filepath}")
        return False
    
    # Try to read first line to ensure it's valid
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if not first_line.strip():
                logging.warning(f"CSV file is empty: {filepath}")
                return False
            if ',' not in first_line and '\t' not in first_line:
                logging.warning(f"CSV file doesn't appear to have delimiters: {filepath}")
                return False
    except Exception as e:
        logging.warning(f"Error reading CSV file: {e}")
        return False
    
    logging.info(f"✅ CSV validation passed ({file_size} bytes)")
    return True


# ---------------------------------------------------------------------------
# Bi-weekly date calculator
# ---------------------------------------------------------------------------
def next_biweekly_date(anchor: datetime.date = BI_WEEKLY_ANCHOR) -> datetime.date:
    """
    Returns next payroll biweekly date including today.
    Examples:
      If today is 04/27 -> returns 04/27
      If today is 04/28 -> returns 05/11
      If today is 05/11 -> returns 05/11
    """
    today = datetime.date.today()
    current = anchor
    while current < today:
        current += datetime.timedelta(days=14)
    return current


# ---------------------------------------------------------------------------
# Screenshot helper
# ---------------------------------------------------------------------------
def shot(page, label: str, out_dir: Path):
    path = out_dir / f"{label}.png"
    page.screenshot(path=str(path))
    print(f"  📸  {path}")


# ---------------------------------------------------------------------------
# Dismiss "Email Reports / Continue Waiting" modal
# ---------------------------------------------------------------------------
def dismiss_email_modal(page, timeout_ms: int = 3000) -> bool:
    """Click 'No' for email dialog or 'Continue Waiting' if the slow-report modal appears. Returns True if dismissed."""
    try:
        # First, try to find and click "No" button on the Email Reports dialog
        no_btn = page.locator("button:has-text('No')")
        no_btn.wait_for(state="visible", timeout=timeout_ms)
        no_btn.click()
        print("  ⚠️   Email Reports dialog dismissed (clicked No)")
        page.wait_for_timeout(1000)
        return True
    except PWTimeout:
        pass
    
    try:
        # Fallback: try "Continue Waiting" button
        btn = page.locator("button:has-text('Continue Waiting')")
        btn.wait_for(state="visible", timeout=timeout_ms)
        btn.click()
        print("  ⚠️   Email-reports modal dismissed")
        page.wait_for_timeout(1000)
        return True
    except PWTimeout:
        return False


# ---------------------------------------------------------------------------
# Click the CSV option from the InfiniteTable body-level portal
# ---------------------------------------------------------------------------
def click_csv_in_portal(page) -> bool:
    """
    The format dropdown renders its options in a body-level portal (InfiniteTable).
    We scan all .InfiniteCell_content_value elements for 'CSV' text and click it.
    Returns True on success.
    """
    try:
        page.wait_for_selector(".InfiniteCell_content_value", timeout=5000)
        cells = page.query_selector_all(".InfiniteCell_content_value")
        for cell in cells:
            if "CSV" in (cell.inner_text() or ""):
                cell.click()
                print("  ✅  CSV option clicked")
                return True
        print("  ⚠️   CSV cell not found in portal — cells found:", [c.inner_text() for c in cells])
        return False
    except PWTimeout:
        print("  ⚠️   InfiniteCell portal never appeared")
        return False


# ---------------------------------------------------------------------------
# Set a React-controlled date input reliably
# ---------------------------------------------------------------------------
def get_date_input_values(page):
    """Return the current values for all visible date inputs."""
    return page.evaluate("""
    () => Array.from(document.querySelectorAll('.DateField__inputWrapper input'))
              .map(inp => inp.value.trim())
    """)


def set_date_field(page, index: int, date_str: str):
    """
    Set a .DateField__inputWrapper input using JS and verify the value.
    index: 0 = first date input, 1 = second date input
    date_str: 'MM/DD/YYYY'
    """
    js_set = f"""
    (() => {{
        const inputs = document.querySelectorAll('.DateField__inputWrapper input');
        const inp = inputs[{index}];
        if (!inp) return 'not found';
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(inp, '');
        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
        nativeSetter.call(inp, '{date_str}');
        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
        inp.blur();
        return inp.value;
    }})()
    """
    result = page.evaluate(js_set)
    print(f"  JS set date[{index}] returned: {result}")

    page.wait_for_timeout(300)
    actual = page.evaluate(f"document.querySelectorAll('.DateField__inputWrapper input')[{index}].value")
    if actual != date_str:
        print(f"  ⚠️   Value did not persist for date[{index}] ({actual}) — retrying with keyboard input")
        inp = page.query_selector_all('.DateField__inputWrapper input')[index]
        inp.click()
        page.wait_for_timeout(300)
        page.keyboard.press('Meta+A')
        page.keyboard.press('Delete')
        page.keyboard.type(date_str, delay=60)
        page.keyboard.press('Tab')
        page.wait_for_timeout(400)
        actual = page.evaluate(f"document.querySelectorAll('.DateField__inputWrapper input')[{index}].value")

    print(f"  ✅  Date[{index}] set to {actual}")


def validate_date_inputs(page, start_date: str, end_date: str):
    values = get_date_input_values(page)
    print(f"  🔎  Date field values: {values}")
    if values == [start_date, end_date]:
        return True
    if values == [end_date, start_date]:
        print("  ⚠️   Date inputs appear swapped; retrying with alternate index mapping")
        set_date_field(page, 0, end_date)
        set_date_field(page, 1, start_date)
        values = get_date_input_values(page)
        print(f"  🔎  Rechecked date field values: {values}")
        return values == [start_date, end_date]
    return False


# ---------------------------------------------------------------------------
# Fire View Report via React web component onClick prop
# ---------------------------------------------------------------------------
def click_view_report(page) -> bool:
    """
    Click the View Report button through React props or DOM fallback.
    """
    js = """
    (() => {
        const buttons = [...document.querySelectorAll('button')].filter(b => b.textContent && b.textContent.trim() === 'View Report');
        if (!buttons.length) return 'button not found';
        const btn = buttons[0];

        const candidates = [btn, btn.parentElement, btn.parentElement && btn.parentElement.parentElement].filter(Boolean);
        for (const candidate of candidates) {
            const propsKey = Object.keys(candidate).find(k => k.startsWith('__reactProps') || k.startsWith('__reactFiber'));
            if (!propsKey) continue;
            const props = candidate[propsKey];
            if (props && typeof props.onClick === 'function') {
                props.onClick({ preventDefault: () => {}, stopPropagation: () => {} });
                return 'react-clicked';
            }
        }

        btn.click();
        return 'dom-clicked';
    })()
    """
    result = page.evaluate(js)
    print(f"  View Report click result: {result}")
    return result in {"react-clicked", "dom-clicked"}


# ---------------------------------------------------------------------------
# Main automation
# ---------------------------------------------------------------------------
def run(username: str, password: str, start_date: str, end_date: str,
        headless: bool, out_dir: Path):

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n🚀  Starting Symplr UAFCompare1 download")
    print(f"    Date range : {start_date} → {end_date}")
    print(f"    Output dir : {out_dir}")
    print(f"    Headless   : {headless}\n")

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless, slow_mo=80)
    ctx = browser.new_context(
        accept_downloads=True,
        viewport={'width': 1280, 'height': 720}
    )
    page = ctx.new_page()
    page.set_default_timeout(int(60_000 * TIMEOUT_BUFFER))  # Add timeout buffer

    try:
        print("Step 1: Logging in …")
        page.goto(LOGIN_URL)
        page.wait_for_load_state("networkidle")
        shot(page, "01_login_page", out_dir)

        page.fill("input[type='text']",     username)
        page.fill("input[type='password']", password)
        page.click("button:has-text('Log In')")
        page.wait_for_timeout(3_000)
        
        # Wait for authentication spinner to disappear (shows "Authenticating...")
        try:
            auth_btn = page.locator("button:has-text('Authenticating')")
            auth_btn.wait_for(state="hidden", timeout=LONG_TIMEOUT)
        except PWTimeout:
            pass
        
        page.wait_for_load_state("networkidle", timeout=NETWORK_TIMEOUT)
        page.wait_for_timeout(2_000)
        shot(page, "02_post_login", out_dir)

        if "LogOn" in page.url:
            shot(page, "ERROR_login_failed", out_dir)
            sys.exit("❌  Login failed — check HIRE_USER / HIRE_PASS")
        print("  ✅  Logged in successfully\n")

        # ── 2. Navigate to Reports ────────────────────────────────────────
        print("Step 2: Navigating to Reports …")
        page.goto(REPORTS_URL)
        page.wait_for_timeout(4_000)
        page.wait_for_load_state("networkidle", timeout=NETWORK_TIMEOUT)
        shot(page, "03_reports_page", out_dir)
        print("  ✅  Reports page loaded\n")

        # ── 3. Click UAFCompare1 ──────────────────────────────────────────
        print("Step 3: Clicking UAFCompare1 …")
        page.wait_for_timeout(2_000)
        # Try multiple selectors to find the UAFCompare1 link
        uaf_link = page.locator("text=UAFCompare1").last
        try:
            uaf_link.wait_for(state="visible", timeout=15_000)
        except PWTimeout:
            print("  ⚠️   First selector failed, trying alternative…")
            uaf_link = page.locator("a:has-text('UAFCompare1')")
            uaf_link.wait_for(state="visible", timeout=10_000)
        
        page.wait_for_timeout(1_000)
        uaf_link.click()
        page.wait_for_timeout(4_000)
        dismiss_email_modal(page)

        try:
            page.wait_for_load_state("networkidle", timeout=LONG_TIMEOUT)
        except PWTimeout:
            pass

        dismiss_email_modal(page)
        shot(page, "04_uafcompare1_loaded", out_dir)
        print("  ✅  UAFCompare1 report opened\n")

        # ── 4. Expand filter panel ────────────────────────────────────────
        print("Step 4: Expanding filter panel …")
        toppane = page.locator(".toppanebtn")
        toppane.wait_for(state="visible", timeout=15_000)
        expanded = page.get_attribute(".toppanebtn", "aria-expanded")
        if expanded != "true":
            toppane.click()
            page.wait_for_timeout(1_500)
        shot(page, "05_filter_panel_open", out_dir)
        print("  ✅  Filter panel expanded\n")

        # ── 5. Set date fields ────────────────────────────────────────────
        print("Step 5: Setting date fields …")
        page.wait_for_selector(".DateField__inputWrapper input", timeout=15_000)
        set_date_field(page, 0, start_date)
        set_date_field(page, 1, end_date)
        page.wait_for_timeout(1_500)

        if not validate_date_inputs(page, start_date, end_date):
            shot(page, "ERROR_date_validation", out_dir)
            raise RuntimeError(f"Date filter validation failed. Expected {start_date}/{end_date}")

        shot(page, "06_dates_set", out_dir)
        print("  ✅  Dates set\n")

        # ── 6. Click View Report ──────────────────────────────────────────
        print("Step 6: Firing View Report …")
        page.wait_for_timeout(2_000)
        success = click_view_report(page)
        if not success:
            # fallback: try physical click on the visible View Report button
            print("  ⚠️   View Report click failed — trying visible button click …")
            page.wait_for_timeout(1_000)
            page.click("button:has-text('View Report')", timeout=15000)

        page.wait_for_timeout(3_000)
        dismiss_email_modal(page, timeout_ms=MODAL_TIMEOUT)

        try:
            page.wait_for_load_state("networkidle", timeout=LONG_TIMEOUT)
        except PWTimeout:
            pass

        page.wait_for_timeout(3_500)
        dismiss_email_modal(page)
        shot(page, "07_report_loaded", out_dir)
        print("  ✅  Report loaded\n")

        # ── 7. Collapse filter panel (optional, cleans viewport) ──────────
        expanded = page.get_attribute(".toppanebtn", "aria-expanded")
        if expanded == "true":
            page.click(".toppanebtn")
            page.wait_for_timeout(1_000)

        # ── 8. Open Export Settings Panel ────────────────────────────────
        print("Step 7: Opening Export panel …")
        page.wait_for_timeout(2_000)
        export_btn = page.locator("[aria-label='Export']")
        export_btn.wait_for(state="visible", timeout=15_000)
        page.wait_for_timeout(1_000)
        export_btn.click()
        page.wait_for_timeout(2_000)
        shot(page, "08_export_panel", out_dir)
        print("  ✅  Export panel opened\n")

        # ── 9. Select CSV format ──────────────────────────────────────────
        print("Step 8: Selecting CSV format …")
        # Click the "Select Format" react-select in the first (Current Layout) row
        page.wait_for_timeout(1_500)
        format_select = page.locator(".ab-ToolPanel__Export__format-select").first
        format_select.wait_for(state="visible", timeout=10_000)
        page.wait_for_timeout(1_000)
        format_select.click()
        page.wait_for_timeout(1_500)
        shot(page, "09_format_dropdown", out_dir)

        if not click_csv_in_portal(page):
            shot(page, "ERROR_csv_not_found", out_dir)
            sys.exit("❌  Could not find CSV option in portal dropdown")

        page.wait_for_timeout(2_000)
        shot(page, "10_csv_selected", out_dir)
        print("  ✅  CSV selected\n")

        # ── 10. Click Download (via DropdownButton arrow) ─────────────────
        print("Step 9: Triggering download …")
        page.wait_for_timeout(2_000)

        # The "Export Report" button is a DropdownButton.
        # We need to click the ARROW part to get the Download/Clipboard submenu.
        # Target the first enabled one (data-name="report-export-selector")
        export_report_btn = page.locator("[data-name='report-export-selector']")
        export_report_btn.wait_for(state="visible", timeout=10_000)
        page.wait_for_timeout(1_000)

        # Get bounding box so we can click the RIGHT edge (arrow)
        bbox = export_report_btn.bounding_box()
        if bbox:
            arrow_x = bbox["x"] + bbox["width"] - 8   # right edge = dropdown arrow
            arrow_y = bbox["y"] + bbox["height"] / 2
            page.mouse.click(arrow_x, arrow_y)
        else:
            # fallback — click by approximate coordinates from confirmed runs
            page.mouse.click(1128, 277)

        page.wait_for_timeout(2_500)
        shot(page, "11_download_submenu", out_dir)

        # Try to find and click the proper export option
        with page.expect_download(timeout=LONG_TIMEOUT) as dl_info:
            download_found = False
            for label in ["Download", "Export Report", "Export"]:
                try:
                    candidate = page.locator(f"text='{label}'").first
                    candidate.wait_for(state="visible", timeout=5_000)
                    print(f"  📥 Clicking menu item: {label}")
                    candidate.click(force=True)
                    download_found = True
                    break
                except PWTimeout:
                    pass

            if not download_found:
                print("  ⚠️   Download/Export option not found. Trying alternative menu items...")
                try:
                    menu_items = page.locator("[role='menuitem'], [role='option'], .submenu-item, button[data-test*='export']").all()
                    if menu_items:
                        for item in menu_items:
                            try:
                                if item.is_visible():
                                    text = (item.inner_text() or "").strip()
                                    if not text:
                                        continue
                                    if "format" in text.lower():
                                        continue
                                    print(f"  📥 Clicking fallback menu item: {text}")
                                    item.click(force=True)
                                    download_found = True
                                    break
                            except Exception as e:
                                logging.warning(f"Fallback menu item click failed: {e}")
                except Exception as e:
                    logging.warning(f"Error while searching fallback menu items: {e}")

            if not download_found:
                print("  ⚠️   Menu item click failed. Trying JS evaluation...")
                clicked = page.evaluate("""
                    () => {
                        const labels = ['Download', 'Export Report', 'Export'];
                        for (const label of labels) {
                            const nodes = [...document.querySelectorAll('*')].filter(el => el.textContent && el.textContent.trim() === label);
                            if (nodes.length) {
                                nodes[0].click();
                                return `${label}-clicked`;
                            }
                        }

                        const fallback = [...document.querySelectorAll('[role="menuitem"], [role="option"], button[class*="export"]')];
                        for (let n of fallback) {
                            const style = window.getComputedStyle(n);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                n.click();
                                return 'fallback-clicked';
                            }
                        }

                        return false;
                    }
                """)
                if not clicked:
                    raise RuntimeError('Could not trigger download - no suitable button found')

        download = dl_info.value
        suggested = download.suggested_filename or f"UAFCompare1_{start_date.replace('/', '-')}.csv"
        
        # Add timestamp to filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = suggested.rsplit('.', 1)  # Split filename and extension
        if len(name_parts) == 2:
            final_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
        else:
            final_filename = f"{suggested}_{timestamp}"
        
        dest = out_dir / final_filename
        download.save_as(str(dest))

        shot(page, "12_download_complete", out_dir)
        
        # Validate the downloaded CSV
        if not validate_csv_file(dest):
            raise RuntimeError(f"CSV validation failed: {dest}")

        print(f"\n✅  Download complete!")
        print(f"    File : {dest}")

        return dest

    except Exception as e:
        logging.error(f"Automation failed: {e}")
        # Take error screenshot if page exists
        try:
            if 'page' in locals() and page:
                shot(page, f"ERROR_{datetime.datetime.now().strftime('%H%M%S')}", out_dir)
        except:
            pass
        raise
    finally:
        # Ensure browser and playwright are closed
        try:
            if browser:
                browser.close()
        except:
            pass
        try:
            if 'pw' in locals():
                pw.stop()
        except:
            pass
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Download UAFCompare1 CSV from Symplr Recruiting")
    parser.add_argument("--start",    help="Start date MM/DD/YYYY  (default: next bi-weekly)")
    parser.add_argument("--end",      help="End date   MM/DD/YYYY  (default: same as start)")
    parser.add_argument("--headless", action="store_true", help="Run without visible browser")
    parser.add_argument("--quiet",    action="store_true", help="Minimal output (for scheduled runs)")
    parser.add_argument("--out",      help="Output directory (default: ~/Downloads/Symplr)")
    args = parser.parse_args()

    # ── Configure logging based on quiet mode ──────────────────────────────
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                handler.setLevel(logging.WARNING)

    # ── Credentials from environment ──────────────────────────────────────
    username = os.environ.get("HIRE_USER", "").strip()
    password = os.environ.get("HIRE_PASS", "").strip()
    if not username or not password:
        sys.exit("❌  Set HIRE_USER and HIRE_PASS environment variables")

    # ── Dates ─────────────────────────────────────────────────────────────
    if args.start:
        # accept YYYY-MM-DD or MM/DD/YYYY
        raw = args.start.replace("-", "/")
        parts = raw.split("/")
        if len(parts[0]) == 4:                    # YYYY/MM/DD
            start_date = f"{parts[1]}/{parts[2]}/{parts[0]}"
        else:
            start_date = raw
    else:
        d = next_biweekly_date()
        start_date = d.strftime("%m/%d/%Y")

    end_date = args.end.replace("-", "/") if args.end else start_date
    if len(end_date.split("/")[0]) == 4:
        p = end_date.split("/")
        end_date = f"{p[1]}/{p[2]}/{p[0]}"

    # ── Output dir ────────────────────────────────────────────────────────
    out_dir_raw = args.out or os.environ.get("DOWNLOAD_DIR", "~/Downloads/Symplr")
    out_dir = Path(out_dir_raw).expanduser().resolve()

    # ── Main execution with retry logic ────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"Attempt {attempt}/{MAX_RETRIES}")
            result = run(username, password, start_date, end_date, args.headless, out_dir)
            if args.quiet:
                print(result)  # Print filepath even in quiet mode
            logging.info(f"✅ Success on attempt {attempt}")
            return result
        except Exception as e:
            logging.error(f"Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * (2 ** (attempt - 1))  # Exponential backoff
                logging.info(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logging.error("❌ All retries exhausted")
                sys.exit(1)


if __name__ == "__main__":
    main()

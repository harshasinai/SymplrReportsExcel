#!/usr/bin/env python3
"""
symplr_uaf_download.py
──────────────────────
Automates login → UAFCompare1 report → CSV download from
Symplr Recruiting (HealthcareSource) for Sinai Chicago.

Usage
-----
  # set credentials once
  export HIRE_USER="your-username"
  export HIRE_PASS="your-password"
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
import json
from pathlib import Path
from typing import Optional
import csv

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

HOLIDAYS = {
    datetime.date(2026, 5, 25),  # Memorial Day
}

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
EXPECTED_LAYOUT_COLUMNS = [
    "Applicant Name", "Email", "Job Title", "Job Code", "Hired Date",
    "Start Date", "Phone", "Recruiter", "Hiring Manager", "Account",
    "Facility", "Facility Code", "Department", "Department Code",
    "Orientation 1 Date",
]

OUTPUT_FILE_PREFIX = "SymplrHireList"


def build_output_filename(now: Optional[datetime.datetime] = None) -> str:
    """Return the standard output CSV name using a 24-hour timestamp."""
    now = now or datetime.datetime.now()
    time_format = "%H%M" if os.name == "nt" else "%H:%M"
    return f"{OUTPUT_FILE_PREFIX}_{now.strftime('%m%d%Y')}_{now.strftime(time_format)}.csv"


def unique_output_path(out_dir: Path, filename: str) -> Path:
    """Avoid overwriting a same-minute export if the script is run twice."""
    dest = out_dir / filename
    if not dest.exists():
        return dest

    stem = dest.stem
    suffix = dest.suffix
    counter = 2
    while True:
        candidate = out_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


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


def validate_csv_columns(filepath: Path, expected_columns):
    """Ensure the first row contains the expected Current Layout columns."""
    try:
        with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            try:
                cols = next(reader)
            except StopIteration:
                logging.warning(f"CSV header row is empty: {filepath}")
                return False
            cols = [c.strip() for c in cols]
            missing = [c for c in expected_columns if c not in cols]
            if missing:
                logging.warning(f"Missing expected CSV columns: {missing}")
                logging.warning(f"Found columns: {cols}")
                return False
    except Exception as e:
        logging.warning(f"Error validating CSV columns: {e}")
        return False
    logging.info(f"✅ CSV contains expected layout columns")
    return True


def extract_table_and_save(page, out_dir: Path, start_date: str):
    """Extract tabular data from the page DOM and save as CSV. Returns Path."""
    js = """
    (() => {
        const visible = el => {
            const s = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        };

        // Prefer AG Grid / ARIA grid output used by this report.
        const grids = Array.from(document.querySelectorAll('[role="grid"]').length ? document.querySelectorAll('[role="grid"]') : []).filter(visible);
        if (grids.length) {
            const grid = grids[0];
            const rowEls = Array.from(grid.querySelectorAll('[role="row"]').length ? grid.querySelectorAll('[role="row"]') : []).filter(visible);
            const rows = rowEls.map(r => Array.from(r.querySelectorAll('[role="gridcell"], [role="cell"]')).map(c => c.innerText.replace(/\\r?\\n/g, ' ').trim()));
            return {type: 'grid', rows};
        }

        // Prefer a large visible table if no ARIA grid exists.
        const tables = Array.from(document.querySelectorAll('table')).filter(visible);
        if (tables.length) {
            const best = tables.reduce((a, b) => (a.rows.length >= b.rows.length ? a : b));
            const rows = Array.from(best.rows).map(r => Array.from(r.cells).map(c => c.innerText.replace(/\\r?\\n/g, ' ').trim()));
            return {type: 'table', rows};
        }

        // Last resort: collect text from visible divs.
        const candidates = Array.from(document.querySelectorAll('div')).filter(visible).map(d => d.innerText.trim()).filter(Boolean);
        return {type: 'text', rows: candidates.slice(0, 200).map(r => [r])};
    })()
    """

    try:
        res = page.evaluate(js)
    except Exception as e:
        raise RuntimeError(f"DOM extraction JS failed: {e}")

    rows = res.get('rows') if isinstance(res, dict) else None
    if not rows:
        raise RuntimeError("No tabular rows found in page DOM")

    # Normalize rows (ensure every row is list of strings)
    norm_rows = []
    max_cols = 0
    for r in rows:
        if not isinstance(r, list):
            r = [str(r)]
        row = [str(c) if c is not None else '' for c in r]
        norm_rows.append(row)
        if len(row) > max_cols:
            max_cols = len(row)

    # Pad rows to equal length
    for i, r in enumerate(norm_rows):
        if len(r) < max_cols:
            norm_rows[i] = r + [''] * (max_cols - len(r))

    dest = unique_output_path(out_dir, build_output_filename())

    with open(dest, 'w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh)
        for row in norm_rows:
            writer.writerow(row)

    # Basic validation
    if not validate_csv_file(dest):
        raise RuntimeError(f"DOM-extracted CSV failed validation: {dest}")

    print(f"\n✅  DOM CSV written: {dest}")
    return dest


# ---------------------------------------------------------------------------
# Bi-weekly date calculator
# ---------------------------------------------------------------------------
def next_business_day(date: datetime.date) -> datetime.date:
    """Move weekends and known holidays to the next weekday."""
    while date.weekday() >= 5 or date in HOLIDAYS:
        date += datetime.timedelta(days=1)
    return date


def next_biweekly_date(
    anchor: datetime.date = BI_WEEKLY_ANCHOR,
    today: Optional[datetime.date] = None,
) -> datetime.date:
    """
    Return the next biweekly report date including today.

    The base schedule stays every 14 days from the anchor. If a scheduled
    date lands on a weekend or known holiday, only that occurrence moves to
    the next business day; future scheduled dates still follow the original
    two-week cadence.

    Examples:
      If today is 05/11/2026 -> returns 05/11/2026
      If today is 05/25/2026 -> returns 05/26/2026 (Memorial Day observed)
      If today is 05/26/2026 -> returns 05/26/2026
      If today is 05/27/2026 -> returns 06/08/2026
    """
    today = today or datetime.date.today()
    scheduled = anchor

    while True:
        report_date = next_business_day(scheduled)
        if report_date >= today:
            return report_date
        scheduled += datetime.timedelta(days=BI_WEEKLY_DAYS)


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
# Dismiss unexpected informational modals
# ---------------------------------------------------------------------------
def dismiss_unexpected_modal(page, timeout_ms: int = 1000) -> bool:
    """Attempt to close known informational popups or modals."""
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() <= deadline:
        try:
            clicked = page.evaluate("""
            () => {
                const labels = ['OK', 'Close', 'Dismiss', 'Got it', 'Remind me later', 'Continue'];
                const closeSelectors = [
                    '[aria-label="Close"]',
                    'button[title="Close"]',
                    '.modal-close',
                    '.dialog-close',
                    '.close-button',
                    '.close'
                ];
                const isVisible = el => {
                    const style = window.getComputedStyle(el);
                    const box = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
                };

                for (const label of labels) {
                    const button = [...document.querySelectorAll('button, [role="button"], a')]
                        .find(el => isVisible(el) && el.textContent.trim() === label);
                    if (button) {
                        button.click();
                        return label;
                    }
                }

                for (const selector of closeSelectors) {
                    const button = [...document.querySelectorAll(selector)].find(isVisible);
                    if (button) {
                        button.click();
                        return selector;
                    }
                }

                return null;
            }
            """)
            if clicked:
                print(f"  ⚠️   Dismissed unexpected modal via: {clicked}")
                page.wait_for_timeout(500)
                return True
        except Exception as e:
            logging.warning(f"Unexpected modal dismiss probe failed: {e}")
            return False

        page.wait_for_timeout(100)
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


def open_export_panel(page) -> bool:
    """Open the ActiveReports export settings panel."""
    try:
        export_btn = page.locator("[aria-label='Export']").first
        export_btn.wait_for(state="visible", timeout=5_000)
        export_btn.click()
        page.wait_for_timeout(2_000)
        return True
    except PWTimeout:
        pass

    # Newer layout may hide Export behind the grid settings gear.
    settings_selectors = [
        "[aria-label='Settings']",
        "[title='Settings']",
        ".ab-Icon--settings",
        ".ab-Icon--gear",
        "button:has(.ab-Icon--settings)",
        "button:has(.ab-Icon--gear)",
    ]
    for selector in settings_selectors:
        try:
            settings = page.locator(selector).first
            settings.wait_for(state="visible", timeout=2_000)
            settings.click()
            page.wait_for_timeout(1_000)

            try:
                export_item = page.get_by_text("Export", exact=True).first
                export_item.wait_for(state="visible", timeout=3_000)
                export_item.click()
            except PWTimeout:
                # Left-side Settings Panel menu item, based on the current layout.
                page.mouse.click(122, 390)

            page.wait_for_timeout(2_000)
            return True
        except PWTimeout:
            continue
        except Exception as e:
            logging.warning(f"Export panel fallback failed for {selector}: {e}")

    return False


def current_layout_export_row(page):
    """Return the visible Export panel row for Report > Current Layout."""
    current_layout = page.locator(
        "div[data-name='selected-option'][data-id='Current Layout']"
    ).first
    current_layout.wait_for(state="visible", timeout=10_000)
    return current_layout.locator("xpath=ancestor::li[@data-name='adaptable-object-list-item'][1]")


def dump_export_debug(page, out_dir: Path, label: str):
    """Save visible export/dropdown candidates for future selector fixes."""
    try:
        debug = page.evaluate("""
        () => {
            const norm = value => (value || '').replace(/\\s+/g, ' ').trim();
            const visible = el => {
                const style = window.getComputedStyle(el);
                const box = el.getBoundingClientRect();
                return style.display !== 'none' &&
                       style.visibility !== 'hidden' &&
                       box.width > 0 &&
                       box.height > 0;
            };

            return [...document.querySelectorAll('button, [role="menuitem"], [role="option"], [data-name], div, li')]
                .filter(el => visible(el))
                .map(el => {
                    const box = el.getBoundingClientRect();
                    return {
                        tag: el.tagName,
                        text: norm(el.textContent).slice(0, 120),
                        role: el.getAttribute('role'),
                        dataName: el.getAttribute('data-name'),
                        ariaLabel: el.getAttribute('aria-label'),
                        className: String(el.className || '').slice(0, 160),
                        rect: {
                            x: Math.round(box.x),
                            y: Math.round(box.y),
                            width: Math.round(box.width),
                            height: Math.round(box.height)
                        }
                    };
                })
                .filter(item => /Download|Clipboard|Export Report|CSV|Current Layout/i.test(
                    [item.text, item.dataName, item.ariaLabel, item.className].filter(Boolean).join(' ')
                ));
        }
        """)
        path = out_dir / f"{label}.json"
        path.write_text(json.dumps(debug, indent=2), encoding="utf-8")
        print(f"  🧾  Export debug saved: {path}")
    except Exception as e:
        logging.warning(f"Export debug dump failed: {e}")


def click_dropdown_option_near(page, label: str, anchor_locator) -> bool:
    """
    Click a visible dropdown option rendered near the anchor button.
    Symplr/Adaptable renders the menu outside the report row, so row-scoped
    locators cannot see the Download option after the dropdown opens.
    """
    anchor = anchor_locator.bounding_box()
    if not anchor:
        raise RuntimeError("Could not locate Export Report dropdown button")

    candidates = page.evaluate("""
    ({ label, anchor }) => {
        const norm = value => (value || '').replace(/\\s+/g, ' ').trim();
        const visible = el => {
            const style = window.getComputedStyle(el);
            const box = el.getBoundingClientRect();
            return style.display !== 'none' &&
                   style.visibility !== 'hidden' &&
                   box.width > 0 &&
                   box.height > 0;
        };
        const clickableAncestor = el => {
            let node = el;
            while (node && node !== document.body) {
                const box = node.getBoundingClientRect();
                const role = node.getAttribute('role') || '';
                const dataName = node.getAttribute('data-name') || '';
                const tag = node.tagName;
                const cursor = window.getComputedStyle(node).cursor;
                const text = norm(node.textContent);
                const clickable = tag === 'BUTTON' ||
                    role === 'menuitem' ||
                    role === 'option' ||
                    Boolean(dataName) ||
                    cursor === 'pointer' ||
                    typeof node.onclick === 'function';

                if (visible(node) &&
                    clickable &&
                    text.includes(label) &&
                    !text.includes('Clipboard') &&
                    box.width >= 40 &&
                    box.height >= 18) {
                    return node;
                }
                node = node.parentElement;
            }
            return el;
        };

        const raw = [...document.querySelectorAll('body *')]
            .filter(el => visible(el) && norm(el.textContent) === label)
            .map(el => clickableAncestor(el));

        const unique = [];
        for (const el of raw) {
            if (!unique.includes(el)) unique.push(el);
        }

        return unique
            .map(el => {
                const box = el.getBoundingClientRect();
                const text = norm(el.textContent);
                return {
                    x: box.x,
                    y: box.y,
                    width: box.width,
                    height: box.height,
                    text,
                    role: el.getAttribute('role') || '',
                    dataName: el.getAttribute('data-name') || '',
                    distance: Math.abs((box.x + box.width / 2) - (anchor.x + anchor.width / 2)) +
                              Math.abs(box.y - (anchor.y + anchor.height))
                };
            })
            .filter(item =>
                item.y >= anchor.y + anchor.height &&
                item.y <= anchor.y + anchor.height + 180 &&
                Math.abs((item.x + item.width / 2) - (anchor.x + anchor.width / 2)) <= 220
            )
            .sort((a, b) => a.distance - b.distance);
    }
    """, {"label": label, "anchor": anchor})

    if candidates:
        candidate = candidates[0]
        page.mouse.click(
            candidate["x"] + candidate["width"] / 2,
            candidate["y"] + candidate["height"] / 2,
        )
        print(
            "  ✅  Clicked dropdown option "
            f"{label!r} at ({candidate['x']:.0f}, {candidate['y']:.0f})"
        )
        return True

    # Last-resort coordinate fallback: first menu row below the dropdown button.
    page.mouse.click(
        anchor["x"] + (anchor["width"] / 2),
        anchor["y"] + anchor["height"] + 20,
    )
    print(f"  ⚠️   Used coordinate fallback for dropdown option {label!r}")
    return True


# ---------------------------------------------------------------------------
# Main automation
# ---------------------------------------------------------------------------
def run(username: str, password: str, start_date: str, end_date: str,
    headless: bool, out_dir: Path, dom_export: bool = False):

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
    page.on("dialog", lambda dialog: dialog.dismiss())
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
        dismiss_unexpected_modal(page)
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
        dismiss_unexpected_modal(page)
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
        dismiss_unexpected_modal(page)

        try:
            page.wait_for_load_state("networkidle", timeout=LONG_TIMEOUT)
        except PWTimeout:
            pass

        dismiss_email_modal(page)
        dismiss_unexpected_modal(page)
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
        dismiss_unexpected_modal(page)

        try:
            page.wait_for_load_state("networkidle", timeout=LONG_TIMEOUT)
        except PWTimeout:
            pass

        page.wait_for_timeout(3_500)
        dismiss_email_modal(page)
        dismiss_unexpected_modal(page)
        shot(page, "07_report_loaded", out_dir)
        print("  ✅  Report loaded\n")

        # If DOM export requested, extract table directly and save CSV
        if dom_export:
            print("  ⚠️   DOM extraction is experimental. Full Current Layout columns may not be visible in the rendered grid.")
            dest = extract_table_and_save(page, out_dir, start_date)
            if not validate_csv_columns(dest, EXPECTED_LAYOUT_COLUMNS):
                raise RuntimeError(
                    f"DOM-exported CSV is missing expected layout fields: {dest}. "
                    "Use the default export path to get the full Current Layout CSV."
                )
            return dest
        # ── 7. Collapse filter panel (optional, cleans viewport) ──────────
        expanded = page.get_attribute(".toppanebtn", "aria-expanded")
        if expanded == "true":
            page.click(".toppanebtn")
            page.wait_for_timeout(1_000)

        # ── 8. Open Export Settings Panel ────────────────────────────────
        print("Step 7: Opening Export panel …")
        page.wait_for_timeout(2_000)
        if not open_export_panel(page):
            shot(page, "ERROR_open_export", out_dir)
            raise RuntimeError("Could not open export panel")
        dismiss_unexpected_modal(page)
        shot(page, "08_export_panel", out_dir)
        print("  ✅  Export panel opened\n")

        # ── 9. Select CSV format ──────────────────────────────────────────
        print("Step 8: Selecting CSV format …")
        # Scope to the first report row: Report > Current Layout.
        page.wait_for_timeout(1_500)
        current_layout_row = current_layout_export_row(page)
        format_select = current_layout_row.locator(".ab-ToolPanel__Export__format-select").first
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

        # ── 10. Open first-row Export Report dropdown, then click Download ─
        print("Step 9: Triggering download …")
        page.wait_for_timeout(2_000)

        shot(page, "11_before_download", out_dir)
        current_layout_row = current_layout_export_row(page)
        export_dropdown_btn = current_layout_row.locator("button[data-name='report-export-selector']").first
        export_dropdown_btn.wait_for(state="visible", timeout=10_000)

        print("  📥 Opening first row Export Report dropdown")
        export_dropdown_btn.click(force=True)
        bbox = export_dropdown_btn.bounding_box()
        if bbox:
            page.mouse.move(
                bbox["x"] + (bbox["width"] / 2),
                bbox["y"] + bbox["height"] + 20,
            )
        page.wait_for_timeout(800)
        shot(page, "11_download_submenu", out_dir)

        try:
            with page.expect_download(timeout=LONG_TIMEOUT) as dl_info:
                print("  📥 Clicking Download")
                click_dropdown_option_near(page, "Download", export_dropdown_btn)
        except PWTimeout:
            shot(page, "ERROR_download_timeout", out_dir)
            dump_export_debug(page, out_dir, "ERROR_download_candidates")
            raise

        download = dl_info.value

        dest = unique_output_path(out_dir, build_output_filename())
        download.save_as(str(dest))

        shot(page, "12_download_complete", out_dir)
        
        # Validate the downloaded CSV
        if not validate_csv_file(dest):
            raise RuntimeError(f"CSV validation failed: {dest}")
        if not validate_csv_columns(dest, EXPECTED_LAYOUT_COLUMNS):
            raise RuntimeError(f"Downloaded CSV is missing expected layout fields: {dest}")

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
    parser.add_argument("--dom",      action="store_true", help="Experimental: extract CSV from page DOM instead of using export (may miss hidden layout columns)")
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
            result = run(username, password, start_date, end_date, args.headless, out_dir, dom_export=args.dom)
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

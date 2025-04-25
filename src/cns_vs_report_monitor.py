import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict
from email_receiver import get_gmail_service
import configparser
from playwright.sync_api import Playwright, sync_playwright
import random
from pdf_report_utils import extract_patient_id_from_pdf, save_pdf_to_db
from db import Session, Referral
import re

# Robust logger setup
log_path = os.path.join(os.path.dirname(__file__), '..', 'cns_vs_report_monitor.log')
logger = logging.getLogger('cns_vs_monitor')
logger.setLevel(logging.INFO)
# Remove all handlers associated with the logger
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
file_handler = logging.FileHandler(log_path)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# Optional: also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.info('TEST LOG ENTRY: Logging is configured and working.')

# Load config
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), '..', 'config.ini'))

# Define reports directory
reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
os.makedirs(reports_dir, exist_ok=True)

def subject_matches_cns_vs(subject: str) -> bool:
    """Return True if subject contains CNS VS report notification phrase (case-insensitive)."""
    return 'cns vital signs online assessment notification' in subject.strip().lower()

def stealth_fill(page, selector, value, min_delay=40, max_delay=120):
    """Fill input fields one character at a time to mimic human typing with random delays."""
    page.locator(selector).fill("")
    for char in value:
        delay = random.randint(min_delay, max_delay)
        page.locator(selector).type(char, delay=delay)

def login_and_download_report(email_data: Dict, username: str, password: str, report_days_back: int = 1) -> bool:
    """
    Uses Playwright to log in to CNS VS and download the relevant report.
    Credentials are passed as parameters for modularity and security.
    Selects the report date as 'report_days_back' days before today.
    Skips download if no report is found for the date.
    """
    # Calculate target date
    target_date = datetime.now() - timedelta(days=report_days_back)
    # Month dropdown is zero-based: 0=Jan, 1=Feb, ..., 3=Apr, ..., 11=Dec
    month_str = str(target_date.month - 1)
    day_str = str(target_date.day)
    logger.info(f"[DATE DEBUG] Calculated target_date: {target_date.strftime('%Y-%m-%d')}, month_str: {month_str}, day_str: {day_str}, report_days_back: {report_days_back}")
    def run(playwright: Playwright) -> bool:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.cnsvs.com/")
        page.get_by_text("Sign In").click()
        page.get_by_text("View Reports and Manage").click()
        # Stealth fill for login
        stealth_fill(page, "#input_user", username)
        stealth_fill(page, "#input_passwd", password)
        page.get_by_role("button", name="Login").click()
        page.get_by_role("button", name="View Reports").click()
        # Wait for the month dropdown option to be attached (present in DOM, not necessarily visible)
        page.wait_for_selector("#reports_first_date_Month_ID option", state="attached")
        month_options = page.evaluate("Array.from(document.querySelectorAll('#reports_first_date_Month_ID option')).map(o => ({value: o.value, text: o.textContent}))")
        logger.info(f"[MONTH DROPDOWN OPTIONS] {month_options}")
        # Select target date for report search (stealth + robust)
        logger.info(f"[DATE DEBUG] Selecting report date: month={month_str}, day={day_str}")
        page.locator("#reports_first_date_Month_ID").select_option(month_str)
        page.evaluate("document.getElementById('reports_first_date_Month_ID').dispatchEvent(new Event('change'))")
        page.locator("#reports_first_date_Day_ID").select_option(day_str)
        page.evaluate("document.getElementById('reports_first_date_Day_ID').dispatchEvent(new Event('change'))")
        # Directly set hidden input for robustness
        page.evaluate(f"document.querySelector('input[name=\\'reports_first_date\\']').value = '{target_date.strftime('%Y-%m-%d')}'")
        page.get_by_role("button", name="Search").click()
        page.get_by_text("Default Report Type: Clinical").click()
        page.get_by_role("button", name="Search").click()
        # After search, find all report rows and download each
        try:
            # Wait for the correct report table to appear
            page.wait_for_selector("table#test_sessions", timeout=10000)
            rows = page.query_selector_all("table#test_sessions tbody tr")
            logger.info(f"Found {len(rows)} report rows (including header).")
            # Skip the first row if it's a header
            for idx, row in enumerate(rows):
                if idx == 0:
                    # Optionally check if this is a header row by inspecting its cells
                    header_cells = row.query_selector_all('th')
                    if header_cells and len(header_cells) > 0:
                        logger.info("Skipping header row.")
                        continue
                try:
                    with page.expect_download() as download_info:
                        row.click()
                    download = download_info.value
                    from datetime import datetime as dt
                    safe_dt = dt.now().strftime('%Y%m%d_%H%M%S_%f')
                    report_filename = f"CNSVS_Report_{safe_dt}.pdf"
                    report_path = os.path.join(reports_dir, report_filename)
                    download.save_as(report_path)
                    # --- Robust file availability check (wait for file to be fully available) ---
                    import time
                    max_wait = 5  # seconds
                    waited = 0
                    while not os.path.exists(report_path) or os.path.getsize(report_path) == 0:
                        logger.info(f"Waiting for file to be fully available: {report_path}")
                        time.sleep(0.5)
                        waited += 0.5
                        if waited >= max_wait:
                            logger.error(f"File {report_path} not available after {max_wait} seconds, skipping.")
                            break
                    else:
                        logger.info(f"File {report_path} is now available and non-empty.")
                    # -------------------------------------------------------------------------
                    # Extract patient ID and store in DB (DEDUPLICATION LOGIC)
                    patient_id = extract_patient_id_from_pdf(report_path)
                    if patient_id:
                        email_id = email_data.get('id', 'unknown')
                        # Deduplication: Check if a report for this patient and date already exists
                        report_date = None
                        match = re.search(r'(\d{8}_\d{6})', report_path)
                        if match:
                            try:
                                report_date = dt.strptime(match.group(1), '%Y%m%d_%H%M%S').date()
                            except Exception:
                                report_date = datetime.now().date()
                        else:
                            report_date = datetime.now().date()
                        duplicate = False
                        with Session() as session:
                            existing = session.query(Referral).filter(
                                Referral.id_number == patient_id,
                                Referral.test_completed == True,
                                Referral.report_processed == True,
                                Referral.report_sent_date != None,
                            ).first()
                            if existing:
                                duplicate = True
                        if duplicate:
                            logger.info(f"Duplicate report found for patient {patient_id} on {report_date}, skipping save.")
                            try:
                                os.remove(report_path)
                                logger.info(f"Deleted duplicate file {report_path}.")
                            except Exception as del_err:
                                logger.warning(f"Failed to delete duplicate file {report_path}: {del_err}")
                        else:
                            save_pdf_to_db(report_path, patient_id, email_id)
                            # --- NEW: Update Referral.pdf_path in DB for orchestrator ---
                            try:
                                with Session() as session:
                                    referral = session.query(Referral).filter(Referral.id_number == patient_id).order_by(Referral.id.desc()).first()
                                    if referral:
                                        referral.pdf_path = report_path
                                        session.commit()
                                        logger.info(f"Updated Referral.pdf_path for patient {patient_id} to {report_path}")
                                    else:
                                        logger.warning(f"No Referral found to update pdf_path for patient {patient_id}")
                            except Exception as db_update_err:
                                logger.error(f"Failed to update Referral.pdf_path for patient {patient_id}: {db_update_err}")
                    else:
                        logger.warning(f"Could not extract patient ID from {report_path}, not saving to DB.")
                except Exception as e:
                    logger.warning(f"Download failed for a report row: {e}")
        except Exception as e:
            logger.warning(f"No report table found or download failed: {e}. Skipping downloads.")
        context.close()
        browser.close()
        return True
    with sync_playwright() as playwright:
        return run(playwright)

def monitor_cns_vs_notifications(max_results: int = 10) -> List[Dict]:
    """Monitor Gmail for CNS VS report notifications and trigger download."""
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', labelIds=['UNREAD'], maxResults=max_results).execute()
    messages = results.get('messages', [])
    matched_emails = []
    username = config.get('cnsvs', 'username', fallback=None)
    password = config.get('cnsvs', 'password', fallback=None)
    report_days_back = config.getint('cnsvs', 'report_days_back', fallback=1)
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        from_ = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date_ = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        snippet = msg_data.get('snippet', '')
        logger.info(f"Checking email subject: {subject}")
        if subject_matches_cns_vs(subject):
            email_data = {
                'subject': subject,
                'from': from_,
                'date': date_,
                'snippet': snippet,
                'id': msg['id']
            }
            logger.info(f"CNS VS notification found: {email_data}")
            if login_and_download_report(email_data, username, password, report_days_back):
                matched_emails.append(email_data)
            # Mark as read
            try:
                service.users().messages().modify(
                    userId='me',
                    id=msg['id'],
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
                logger.info(f"Marked CNS VS email {msg['id']} as read.")
            except Exception as e:
                logger.error(f"Failed to mark CNS VS email {msg['id']} as read: {e}")
        else:
            logger.info(f"Skipping non-CNS VS email: {subject}")
    logger.info(f"Processed {len(matched_emails)} CNS VS notifications.")
    return matched_emails

if __name__ == '__main__':
    monitor_cns_vs_notifications()

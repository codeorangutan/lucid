import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict
from email_receiver import get_gmail_service
import configparser
from playwright.sync_api import Playwright, sync_playwright
import random
from pdf_report_utils import extract_patient_id_from_pdf, save_pdf_to_db

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
        # Try to find the report cell, skip download if not found
        try:
            cell = page.get_by_role("cell", name="LucidCognitiveTesting@gmail.")
            if not cell.is_visible():
                logger.info(f"No report found for date {target_date.strftime('%Y-%m-%d')}. Skipping download.")
                context.close()
                browser.close()
                return False
            with page.expect_download() as download_info:
                cell.click()
            download = download_info.value
            # Use a robust, timestamped filename
            from datetime import datetime as dt
            safe_dt = dt.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"CNSVS_Report_{safe_dt}.pdf"
            report_path = os.path.join(reports_dir, report_filename)
            download.save_as(report_path)
            logger.info(f"Downloaded CNS VS report for: {email_data.get('subject')} / {email_data.get('date')} to {report_path}")
            # Extract patient ID and store in DB
            patient_id = extract_patient_id_from_pdf(report_path)
            if patient_id:
                email_id = email_data.get('id', 'unknown')
                save_pdf_to_db(report_path, patient_id, email_id)
            else:
                logger.warning(f"Could not extract patient ID from {report_path}, not saving to DB.")
        except Exception as e:
            logger.warning(f"No report cell found or download failed: {e}. Skipping download.")
            context.close()
            browser.close()
            return False
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

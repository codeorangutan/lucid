import logging
import random
import time
import os
import configparser
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PlaywrightTimeoutError

# Robust logger setup
log_path = os.path.join(os.path.dirname(__file__), '..', 'lucid_request.log')
logger = logging.getLogger('lucid_request')
logger.setLevel(logging.INFO)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
file_handler = logging.FileHandler(log_path)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.info('TEST LOG ENTRY: Logging is configured and working.')

# Load config
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), '..', 'config.ini'))

def stealth_delay(min_delay=0.8, max_delay=2.2):
    """Wait for a random period between min_delay and max_delay seconds."""
    delay = random.uniform(min_delay, max_delay)
    logger.debug(f"Stealth delay: sleeping for {delay:.2f} seconds.")
    time.sleep(delay)

def request_cns_remote_test(playwright: Playwright, subject: str, dob_year: str, email: str):
    browser = None
    context = None
    try:
        logger.info(f"Starting browser automation for subject={subject}, dob_year={dob_year}, email={email}")
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.cnsvs.com/")
        logger.info("Navigated to CNSVS homepage.")
        stealth_delay()
        page.get_by_text("Sign In").click()
        stealth_delay()
        page.get_by_text("Generate Remote Test Code").click()
        stealth_delay()
        # Use credentials from config file
        username = config.get('cnsvs', 'username', fallback=None)
        password = config.get('cnsvs', 'password', fallback=None)
        page.locator("#input_user").click()
        stealth_delay()
        page.locator("#input_user").fill(username)
        stealth_delay()
        page.locator("#input_passwd").click()
        stealth_delay()
        page.locator("#input_passwd").fill(password)
        stealth_delay()
        page.get_by_role("button", name="Login").click()
        logger.info(f"Logged in as {username}.")
        stealth_delay()
        page.get_by_role("combobox").select_option("english_uk")
        stealth_delay()
        page.get_by_role("button", name="Initial ADHD").click()
        stealth_delay()
        page.locator("#input_subject").click()
        stealth_delay()
        page.locator("#input_subject").fill(subject)
        stealth_delay()
        page.locator("#dob_year").click()
        stealth_delay()
        page.locator("#dob_year").fill(dob_year)
        stealth_delay()
        page.locator("#dob_month").click()
        stealth_delay()
        page.locator("#dob_month").fill("Jan")
        stealth_delay()
        page.locator("#dob_day").click()
        stealth_delay()
        page.locator("#dob_day").fill("1")
        stealth_delay()
        page.get_by_role("button", name="Add New Remote Test Code").click()
        logger.info(f"Requested remote test for subject={subject}, dob_year={dob_year}")
        stealth_delay()
        page.once("dialog", lambda dialog: dialog.dismiss())
        logger.info("Dismissed dialog if present.")
        stealth_delay()
        page.locator("button[name=\"SHFNHJWBB\"]").click()
        stealth_delay()
        page.once("dialog", lambda dialog: dialog.dismiss())
        stealth_delay()
        page.goto(f"https://sync.cnsvs.com/sync.php?menu=remote_test&email_code=HFNHJWBB&email_to={email}")
        logger.info(f"Sent remote test to {email}")
    except PlaywrightTimeoutError as te:
        logger.error(f"Timeout occurred: {te}")
    except Exception as e:
        logger.exception(f"An error occurred during automation: {e}")
    finally:
        if context:
            context.close()
        if browser:
            browser.close()
        logger.info("Browser session closed.")

if __name__ == "__main__":
    with sync_playwright() as playwright:
        # Example usage
        request_cns_remote_test(playwright, subject="11112", dob_year="2000", email="sford359@gmail.com")

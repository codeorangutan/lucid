import logging
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("lucid_request.log"),
        logging.StreamHandler()
    ]
)

def request_cns_remote_test(playwright: Playwright, subject: str, dob_year: str, email: str):
    browser = None
    context = None
    try:
        logging.info(f"Starting browser automation for subject={subject}, dob_year={dob_year}, email={email}")
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.cnsvs.com/")
        logging.info("Navigated to CNSVS homepage.")
        page.get_by_text("Sign In").click()
        page.get_by_text("Generate Remote Test Code").click()
        page.locator("#input_user").click()
        page.locator("#input_user").fill("LucidCognitiveTesting@gmail.com")
        page.locator("#input_passwd").click()
        page.locator("#input_passwd").fill("pD4,V:#_SOfS")
        page.get_by_role("button", name="Login").click()
        logging.info("Logged in as LucidCognitiveTesting.")
        page.get_by_role("combobox").select_option("english_uk")
        page.get_by_role("button", name="Initial ADHD").click()
        page.locator("#input_subject").click()
        page.locator("#input_subject").fill(subject)
        page.locator("#dob_year").click()
        page.locator("#dob_year").fill(dob_year)
        page.locator("#dob_month").click()
        page.locator("#dob_month").fill("Jan")
        page.locator("#dob_day").click()
        page.locator("#dob_day").fill("1")
        page.get_by_role("button", name="Add New Remote Test Code").click()
        logging.info(f"Requested remote test for subject={subject}, dob_year={dob_year}")
        page.once("dialog", lambda dialog: dialog.dismiss())
        logging.info("Dismissed dialog if present.")
        page.locator("button[name=\"SHFNHJWBB\"]").click()
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.goto(f"https://sync.cnsvs.com/sync.php?menu=remote_test&email_code=HFNHJWBB&email_to={email}")
        logging.info(f"Sent remote test to {email}")
    except PlaywrightTimeoutError as te:
        logging.error(f"Timeout occurred: {te}")
    except Exception as e:
        logging.exception(f"An error occurred during automation: {e}")
    finally:
        if context:
            context.close()
        if browser:
            browser.close()
        logging.info("Browser session closed.")

if __name__ == "__main__":
    with sync_playwright() as playwright:
        # Example usage
        request_cns_remote_test(playwright, subject="11112", dob_year="2000", email="sford359@gmail.com")

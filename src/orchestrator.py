"""
LUCID Orchestrator Script (Polling Model)

- See detailed plan in: src/plans/Orchestration Plan.md
- This script is the central polling controller for the LUCID workflow.
- Each stage is modular, idempotent, and robustly logged.
- Run every 10 minutes via cron or Task Scheduler.

# Orchestration Stage Flags (set as environment variables):
#   ORCH_STAGE_INTAKE=0           # Disable Intake: Process New Referrals
#   ORCH_STAGE_TEST_REQUEST=0     # Disable Test Request: Initiate CNS Test
#   ORCH_STAGE_REPORT_MONITOR=0   # Disable Report Monitoring: Detect Test Completion
#   ORCH_STAGE_REPORT_PROCESS=0   # Disable Report Processing: Reformat and Save
#   ORCH_STAGE_REPORT_DELIVERY=0  # Disable Report Delivery: Email to Referrer
#   ORCH_STAGE_REMINDERS=0        # Disable Reminders: Nagging for Incomplete Tests
#   ORCH_STAGE_RESEND_LINKS=0     # Disable Resend Link Requests
# All are enabled by default (set to 1 or unset)
"""
import logging
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Import necessary DB components
from db import Session, Referral, save_referral

# TODO: Import other modules as needed
# from email_receiver import ... # Moved import inside function to avoid circular dependency if email_receiver imports orchestrator components later
# from process_existing_reports import ...
# from db import ...

def is_stage_enabled(env_var, default=True):
    val = os.environ.get(env_var)
    if val is None:
        return default
    return val.strip() not in ('0', 'false', 'False', '')

# Logging setup
log_path = os.path.join(os.path.dirname(__file__), '..', 'lucid_orchestrator.log')
logger = logging.getLogger('lucid_orchestrator')
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
logger.info('Orchestrator started.')

# --- Pipeline Stage Functions ---
def process_new_referrals():
    """Intake: Detect new referrals via email, validate, and save to DB."""
    logger.info("[STAGE] Processing new referrals...")
    saved_count = 0
    try:
        # Import the function that now returns data
        from email_receiver import list_unread_emails_gmail_api
        # Get the list of potential referrals
        potential_referrals = list_unread_emails_gmail_api(max_results=10) # Fetch data
        logger.info(f"Fetched {len(potential_referrals)} potential referral email(s).")

        if not potential_referrals:
            return

        # Process each potential referral
        # Use a single session for this batch to be efficient
        with Session() as session:
            for data in potential_referrals:
                parsed = data.get('parsed', {})
                subject = data.get('subject', '')
                body = data.get('body', '')
                referrer_email = data.get('referrer_email', '') # Extracted 'From' address
                received_time = data.get('referral_received_time')

                # --- Validation Logic ---
                # 1. Check for essential data (e.g., patient email)
                patient_email = parsed.get('email')
                if not patient_email:
                    logger.warning(f"Skipping referral from {referrer_email} - missing patient email. Subject: {subject}")
                    continue # Skip this referral

                # 2. Optional: Check for recent duplicates for the same patient email
                # Look for referrals with the same email received in the last hour (adjust timeframe as needed)
                # time_threshold = datetime.now() - timedelta(hours=1)
                # existing = session.query(Referral).filter(
                #     Referral.email == patient_email,
                #     Referral.referral_received_time >= time_threshold
                # ).first()
                # if existing:
                #     logger.info(f"Skipping potentially duplicate referral for {patient_email} received recently.")
                #     continue # Skip this duplicate
                # --- End Validation ---

                # If validation passes, save the referral
                try:
                    # Call the save function from db module
                    save_referral(
                        parsed=parsed,
                        subject=subject,
                        body=body,
                        # Extract referrer name if available, otherwise use email
                        referrer=referrer_email.split('<')[0].strip() if '<' in referrer_email else referrer_email,
                        referrer_email=referrer_email.split('<')[-1].replace('>', '').strip() if '<' in referrer_email else referrer_email,
                        referral_received_time=received_time,
                        # Add referral_confirmed_time if applicable/available from email_receiver data
                        # referral_confirmed_time=data.get('referral_confirmed_time')
                    )
                    saved_count += 1
                    logger.info(f"Successfully saved referral for patient email: {patient_email}")
                except Exception as db_err:
                    # Log error but continue processing other referrals
                    logger.error(f"Failed to save referral for patient email {patient_email} from {referrer_email}: {db_err}")
                    # Consider more sophisticated error handling if needed (e.g., rollback)

        logger.info(f"Attempted to save {len(potential_referrals)} referrals, successfully saved {saved_count}.")

    except Exception as e:
        # Catch errors during email fetching or general processing
        logger.exception(f"Error in 'process_new_referrals' stage: {e}")


def request_tests_for_pending_patients(headless=True):
    """Trigger Playwright automation for pending test requests."""
    logger.info("[STAGE] Requesting tests for pending patients...")
    from db import Session, Referral
    from datetime import datetime
    from playwright.sync_api import sync_playwright
    try:
        with Session() as session:
            pending_patients = session.query(Referral).filter(
                Referral.test_request_time == None
            ).all()
            logger.info(f"Found {len(pending_patients)} patient(s) needing test requests.")
            if not pending_patients:
                return
            with sync_playwright() as playwright:
                for patient in pending_patients:
                    try:
                        logger.info(f"Requesting test for patient: {patient.id_number}, email: {patient.email}, dob: {patient.dob}")
                        # Extract year from dob (fallback to '2000' if missing)
                        dob_year = str(patient.dob).split("-")[0] if patient.dob else "2000"
                        from request_cns_test import request_cns_remote_test
                        request_cns_remote_test(
                            playwright,
                            subject=patient.id_number or str(patient.id),
                            dob_year=dob_year,
                            email=patient.email,
                            headless=headless
                        )
                        patient.test_request_time = datetime.now()
                        session.commit()
                        logger.info(f"Test requested for patient {patient.id_number}.")
                    except Exception as e:
                        logger.exception(f"Error requesting test for patient {patient.id_number}: {e}")
    except Exception as e:
        logger.exception(f"Error in test request stage: {e}")

def process_new_reports():
    """Monitor for and process new report notification emails."""
    logger.info("[STAGE] Monitoring for new CNS VS report notifications...")
    try:
        from cns_vs_report_monitor import monitor_cns_vs_notifications
        matched = monitor_cns_vs_notifications(max_results=10)
        logger.info(f"Processed {len(matched)} CNS VS report notification(s).")
    except Exception as e:
        logger.exception(f"Error processing new CNS VS reports: {e}")

def reformat_and_save_reports():
    """Reformat downloaded reports and save to DB (template)."""
    logger.info("[STAGE] Reformatting and saving reports (TEMPLATE ONLY)...")
    # TODO: Implement report reformatting logic once the feature branch is merged.
    # Example:
    # from report_reformatter import reformat_report
    # for report in get_downloaded_reports():
    #     reformatted = reformat_report(report)
    #     save_reformatted_report_to_db(reformatted)
    pass

def send_reports_to_referrers():
    """Email reformatted reports to referrers."""
    logger.info("[STAGE] Sending reports to referrers...")
    # Template implementation: fill in when report reformatter is merged
    # Example logic:
    # from db import Session, Referral
    # with Session() as session:
    #     reports_to_send = session.query(Referral).filter(
    #         Referral.report_processed == True,
    #         Referral.report_sent_date == None
    #     ).all()
    #     for referral in reports_to_send:
    #         # send_email_with_attachment(referral.referrer_email, ...)
    #         referral.report_sent_date = datetime.now()
    #         session.commit()
    #         logger.info(f"Report sent to {referral.referrer_email}")
    logger.info("[TEMPLATE] Report delivery logic will be implemented after report formatting is finalized.")
    pass

def send_reminders():
    """Send reminders for incomplete tests with escalating urgency and expiry notifications."""
    logger.info("[STAGE] Sending reminders for incomplete tests...")
    from db import Session, Referral
    from datetime import datetime, timedelta
    # Reminder schedule in days/hours
    REMINDER_STEPS = [
        (7, "Must complete test within 7 days. Please use your link to begin your cognitive assessment."),
        (3, "Reminder: You have 3 days left to complete your cognitive assessment. Please use your link."),
        (1, "Urgent: You have 1 day left to complete your cognitive assessment. Please use your link."),
        (0.5, "Final reminder: You have 12 hours left to complete your cognitive assessment. Please use your link."),
        (1/24, "Final reminder: You have 1 hour left to complete your cognitive assessment. Please use your link."),
        (0, "Your test link has expired. Please contact your referrer if you still wish to complete the assessment.")
    ]
    try:
        with Session() as session:
            now = datetime.now()
            referrals = session.query(Referral).filter(
                Referral.test_request_time != None,
                Referral.test_completed == False
            ).all()
            logger.info(f"Found {len(referrals)} patient(s) with pending tests for reminders.")
            for patient in referrals:
                if not patient.test_request_time:
                    continue
                delta = (now - patient.test_request_time).total_seconds() / 86400  # days since request
                reminder_text = None
                for days, text in REMINDER_STEPS:
                    if delta >= days:
                        reminder_text = text
                        break
                if reminder_text:
                    # Placeholder for actual email/SMS logic
                    logger.info(f"Would send reminder to {patient.email} (test requested {patient.test_request_time}): {reminder_text}")
                    # TODO: Integrate with actual reminder sending function (email/SMS)
    except Exception as e:
        logger.exception(f"Error in reminder stage: {e}")

def enforce_safety_limits():
    """Enforce safety limits on requests per day, per patient."""
    logger.info("[STAGE] Enforcing safety limits...")
    from db import Session, Referral
    from datetime import datetime, timedelta
    # Example limits (configurable)
    MAX_REQUESTS_PER_PATIENT_PER_DAY = 1
    MAX_TOTAL_REQUESTS_PER_DAY = 20
    try:
        with Session() as session:
            today = datetime.now().date()
            # Check per-patient limit
            patients = session.query(Referral.id_number).distinct().all()
            for (id_number,) in patients:
                count = session.query(Referral).filter(
                    Referral.id_number == id_number,
                    Referral.test_request_time != None,
                    Referral.test_request_time >= datetime.combine(today, datetime.min.time()),
                    Referral.test_request_time < datetime.combine(today + timedelta(days=1), datetime.min.time())
                ).count()
                if count > MAX_REQUESTS_PER_PATIENT_PER_DAY:
                    logger.warning(f"Patient {id_number} exceeded daily request limit: {count}")
            # Check global daily limit
            total_today = session.query(Referral).filter(
                Referral.test_request_time != None,
                Referral.test_request_time >= datetime.combine(today, datetime.min.time()),
                Referral.test_request_time < datetime.combine(today + timedelta(days=1), datetime.min.time())
            ).count()
            if total_today > MAX_TOTAL_REQUESTS_PER_DAY:
                logger.warning(f"Total requests today exceeded daily limit: {total_today}")
    except Exception as e:
        logger.exception(f"Error in safety limits enforcement: {e}")

def process_resend_link_requests():
    """Detects and processes 'resend link' requests for expired test links."""
    logger.info("[STAGE] Processing resend test link requests...")
    from db import Session, Referral
    from datetime import datetime, timedelta
    try:
        # TODO: Replace with actual email parsing logic for 'resend link' requests
        from email_receiver import list_resend_link_requests
        resend_requests = list_resend_link_requests(max_results=10)
        with Session() as session:
            for req in resend_requests:
                # req should contain a patient identifier (email or id_number)
                patient = session.query(Referral).filter(
                    (Referral.email == req['email']) | (Referral.id_number == req['id_number']),
                    Referral.test_completed == False
                ).first()
                if not patient:
                    logger.info(f"No matching patient found for resend request: {req}")
                    continue
                if patient.test_request_time and (datetime.now() - patient.test_request_time).days >= 7:
                    # Trigger new test order
                    from request_cns_test import request_cns_remote_test
                    request_cns_remote_test(
                        None,  # playwright instance if needed
                        subject=patient.id_number or str(patient.id),
                        dob_year=str(patient.dob).split("-")[0] if patient.dob else "2000",
                        email=patient.email,
                        headless=True
                    )
                    patient.test_resent = True
                    patient.test_resent_time = datetime.now()
                    session.commit()
                    logger.info(f"Test resent for patient {patient.id_number} at {patient.test_resent_time}")
                else:
                    logger.info(f"Patient {patient.id_number} not eligible for resend (not enough time elapsed)")
    except Exception as e:
        logger.exception(f"Error processing resend link requests: {e}")

def parse_and_upload_reports():
    """Parse downloaded reports and upload structured data to the DB."""
    logger.info("[STAGE] Parsing and uploading new reports...")
    from db import Session, Referral
    import subprocess
    import sys
    try:
        with Session() as session:
            # Find referrals with unprocessed reports (PDF downloaded, not yet parsed)
            referrals = session.query(Referral).filter(
                Referral.report_unprocessed == True
            ).all()
            logger.info(f"Found {len(referrals)} report(s) to parse.")
            for referral in referrals:
                try:
                    # Assume PDF path is stored in a field, e.g., referral.pdf_path (add if missing)
                    pdf_path = getattr(referral, 'pdf_path', None)
                    if not pdf_path or not os.path.exists(pdf_path):
                        logger.warning(f"No valid PDF path for referral ID {referral.id}, skipping.")
                        continue
                    # Call cognitive_importer.py as subprocess (for isolation and error capture)
                    result = subprocess.run([
                        sys.executable, '-m', 'report_refactor.cognitive_importer', pdf_path
                    ], capture_output=True, text=True)
                    if result.returncode == 0:
                        # On success, update status
                        referral.report_unprocessed = False
                        referral.report_processed = True
                        session.commit()
                        logger.info(f"Parsed and uploaded report for referral ID {referral.id}.")
                    else:
                        logger.error(f"Parser failed for referral ID {referral.id}: {result.stderr}")
                except Exception as parse_err:
                    logger.exception(f"Error parsing report for referral ID {referral.id}: {parse_err}")
    except Exception as e:
        logger.exception(f"Error in parse_and_upload_reports stage: {e}")

def main():
    logger.info("--- LUCID Orchestration Cycle Start ---")
    try:
        if is_stage_enabled('ORCH_STAGE_INTAKE'):
            process_new_referrals()
        else:
            logger.info('[SKIP] Intake: Process New Referrals')
        if is_stage_enabled('ORCH_STAGE_TEST_REQUEST'):
            request_tests_for_pending_patients()
        else:
            logger.info('[SKIP] Test Request: Initiate CNS Test')
        if is_stage_enabled('ORCH_STAGE_REPORT_MONITOR'):
            process_new_reports()
        else:
            logger.info('[SKIP] Report Monitoring: Detect Test Completion')
        if is_stage_enabled('ORCH_STAGE_REPORT_PROCESS'):
            parse_and_upload_reports()
        else:
            logger.info('[SKIP] Report Processing: Parse and Upload')
        if is_stage_enabled('ORCH_STAGE_REPORT_DELIVERY'):
            send_reports_to_referrers()
        else:
            logger.info('[SKIP] Report Delivery: Email to Referrer')
        if is_stage_enabled('ORCH_STAGE_REMINDERS'):
            send_reminders()
        else:
            logger.info('[SKIP] Reminders: Nagging for Incomplete Tests')
        if is_stage_enabled('ORCH_STAGE_RESEND_LINKS'):
            process_resend_link_requests()
        else:
            logger.info('[SKIP] Resend Link Requests')
        enforce_safety_limits()  # Always enforce safety limits
    except Exception as e:
        logger.exception(f"Orchestration error: {e}")
    logger.info("--- LUCID Orchestration Cycle End ---\n")

if __name__ == "__main__":
    main()

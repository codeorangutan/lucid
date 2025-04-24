import logging
import os
import pickle
import email
from typing import List, Dict
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import re
import base64
from datetime import datetime

# Robust logger setup
log_path = os.path.join(os.path.dirname(__file__), '..', 'lucid_email_receiver.log')
logger = logging.getLogger('lucid_email_receiver')
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

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_PATH = os.path.join('credentials', 'credentials.json')
TOKEN_PATH = os.path.join('credentials', 'token.pickle')

def get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def parse_email_body(body: str) -> dict:
    """Extract mobile, email, dob, and id number from the email body text."""
    result = {}
    # Mobile phone (Australian/international/general, flexible)
    mobile_match = re.search(r'(?:(?:\+?61|0)[2-478])(?:[ -]?\d){8}', body)
    if not mobile_match:
        mobile_match = re.search(r'\b\d{10,12}\b', body)
    result['mobile'] = mobile_match.group(0) if mobile_match else None
    # Email address
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', body)
    result['email'] = email_match.group(0) if email_match else None
    # Date of birth (formats: dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy, etc.)
    dob_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b', body)
    result['dob'] = dob_match.group(0) if dob_match else None
    # ID number (5 digits)
    id_match = re.search(r'\b\d{5}\b', body)
    result['id_number'] = id_match.group(0) if id_match else None
    return result

def get_email_body(msg_data):
    """Extract and decode the plain text body from Gmail API message data."""
    payload = msg_data.get('payload', {})
    parts = payload.get('parts', [])
    body = ''
    # Try to find the plain text part
    for part in parts:
        if part.get('mimeType') == 'text/plain':
            body_data = part['body'].get('data', '')
            if body_data:
                body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                break
    if not body and 'body' in payload and 'data' in payload['body']:
        # Fallback: single-part message
        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')
    return body

def subject_matches(subject: str) -> bool:
    """Check if the subject contains 'Referral' or 'Cognitive Testing' (case-insensitive)."""
    keywords = ['referral', 'cognitive testing']
    subject_lower = subject.lower()
    return any(keyword in subject_lower for keyword in keywords)

def send_reply_email(service, original_msg, reply_to):
    """Send a reply to the sender with a canned message."""
    from email.mime.text import MIMEText
    import base64 as b64
    reply_text = "Referral was received and a test will be sent to the patient."
    subject = "Re: " + next((h['value'] for h in original_msg['payload'].get('headers', []) if h['name'] == 'Subject'), '')
    message = MIMEText(reply_text)
    message['to'] = reply_to
    message['subject'] = subject
    message['In-Reply-To'] = original_msg['id']
    raw = b64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        logger.info(f"Sent reply to {reply_to} for message {original_msg['id']}")
    except Exception as e:
        logger.error(f"Failed to send reply email: {e}")

def list_unread_emails_gmail_api(max_results: int = 10) -> List[Dict]:
    """Fetch unread emails from Gmail API, mark them as read, parse body, filter by subject."""
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=max_results).execute()
    messages = results.get('messages', [])
    processed_emails = []

    if not messages:
        logger.info("No unread messages found in Gmail API.")

    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        from_ = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date_ = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        snippet = msg_data.get('snippet', '')
        body = get_email_body(msg_data)
        parsed = parse_email_body(body)
        logger.info(f"Parsed email ID {msg['id']} from {from_}: {parsed}")

        # Collect data instead of saving
        referral_data = {
            'parsed': parsed,
            'subject': subject,
            'body': body,
            'referrer_email': from_,  # Assuming 'From' is the referrer email
            'referral_received_time': datetime.now()  # Or parse from date_str if needed
            # Add other relevant fields extracted from headers/body if necessary
        }
        processed_emails.append(referral_data)

        # Mark as read after successful parsing
        service.users().messages().modify(
            userId='me',
            id=msg['id'],
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        logger.info(f"Marked email {msg['id']} as read.")

    logger.info(f"Processed {len(processed_emails)} relevant unread emails from Gmail API.")
    return processed_emails

def list_resend_link_requests(max_results: int = 10):
    """
    Fetch unread emails from Gmail API that are likely 'link expired' or 'resend link' requests.
    Returns a list of dicts: [{'email': ..., 'id_number': ...}, ...]
    """
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=max_results).execute()
    messages = results.get('messages', [])
    resend_requests = []
    KEYWORDS = [
        'link expired', 'resend link', 'test expired', 'need new link', 'cannot access test',
        'link not working', 'test link expired', 'send new link'
    ]
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        from_ = next((h['value'] for h in headers if h['name'] == 'From'), '')
        body = get_email_body(msg_data)
        # Check for resend keywords in subject or body
        text = f"{subject}\n{body}".lower()
        if any(keyword in text for keyword in KEYWORDS):
            parsed = parse_email_body(body)
            # At minimum, try to get email or id_number
            patient_id = {}
            if parsed.get('email'):
                patient_id['email'] = parsed['email']
            if parsed.get('id_number'):
                patient_id['id_number'] = parsed['id_number']
            if patient_id:
                resend_requests.append(patient_id)
                logger.info(f"Detected resend link request: {patient_id} from {from_}")
        # Mark as read
        service.users().messages().modify(
            userId='me',
            id=msg['id'],
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        logger.info(f"Marked email {msg['id']} as read (resend link request).")
    logger.info(f"Fetched {len(resend_requests)} resend link requests from Gmail API.")
    return resend_requests

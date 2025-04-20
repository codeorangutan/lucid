import logging
import os
import pickle
import imaplib
import email
from typing import List, Dict
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import re
import base64
from datetime import datetime
from db import save_referral

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
        logger.error(f"Failed to send reply: {e}")

def list_unread_emails_gmail_api(max_results: int = 10) -> List[Dict]:
    """Fetch unread emails from Gmail API, mark them as read, parse body, filter by subject, and send reply."""
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', labelIds=['UNREAD'], maxResults=max_results).execute()
    messages = results.get('messages', [])
    emails = []
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
        # extract referrer and referrer_email from 'from_' header
        if '<' in from_:
            referrer = from_.split('<')[0].strip()
            referrer_email = from_.split('<')[1].replace('>', '').strip()
        else:
            referrer = from_
            referrer_email = from_
        referral_received_time = datetime.now()
        if subject_matches(subject):
            required_fields = ['email', 'id_number']  # Add more if needed
            missing = [f for f in required_fields if not parsed.get(f)]
            if missing:
                logger.warning(f"Skipping referral: missing required fields {missing}. Subject: {subject}")
                continue
            emails.append({
                'subject': subject,
                'from': from_,
                'date': date_,
                'snippet': snippet,
                'id': msg['id'],
                'body': body,
                'parsed': parsed,
                'referrer': referrer,
                'referrer_email': referrer_email,
                'referral_received_time': referral_received_time.isoformat()
            })
            # Log parsed data
            logger.info(f"Parsed data for email {msg['id']}: {parsed}")
            logger.info(f"Referral received at {referral_received_time.isoformat()} from {referrer_email}")
            # Save to database
            save_referral(parsed, subject, body, referrer, referrer_email, referral_received_time)
            # Send reply
            reply_to = referrer_email
            send_reply_email(service, msg_data, reply_to)
        # Mark as read
        try:
            service.users().messages().modify(
                userId='me',
                id=msg['id'],
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            logger.info(f"Marked email {msg['id']} as read.")
        except Exception as e:
            logger.error(f"Failed to mark email {msg['id']} as read: {e}")
    logger.info(f"Fetched {len(emails)} relevant unread emails from Gmail API.")
    return emails

def list_unread_emails(imap_host: str, email_user: str, email_pass: str, mailbox: str = 'INBOX') -> List[Dict]:
    """
    Connects to the IMAP server and returns a list of unread email headers.
    Returns: list of dicts: [{subject, from, date, uid}, ...]
    """
    emails = []
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(email_user, email_pass)
        mail.select(mailbox)
        status, data = mail.search(None, 'UNSEEN')
        if status != 'OK':
            logger.warning(f"No unread emails found.")
            return emails
        for num in data[0].split():
            status, msg_data = mail.fetch(num, '(RFC822)')
            if status != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = email.header.decode_header(msg['Subject'])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode(errors='replace')
            from_ = msg.get('From', '')
            date_ = msg.get('Date', '')
            emails.append({'subject': subject, 'from': from_, 'date': date_, 'uid': num.decode()})
        logger.info(f"Fetched {len(emails)} unread emails.")
        return emails
    except Exception as e:
        logger.exception(f"Error fetching unread emails: {e}")
        return emails
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass

import os
import pickle
from typing import List, Dict
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import logging

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_PATH = os.path.join('credentials', 'credentials.json')
TOKEN_PATH = os.path.join('credentials', 'token.pickle')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("lucid_gmail_integration.log"),
        logging.StreamHandler()
    ]
)

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

def fetch_unread_emails(max_results: int = 10) -> List[Dict]:
    """Fetch unread emails and return a list of dicts with subject, from, date, and snippet."""
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', labelIds=['UNREAD'], maxResults=max_results).execute()
    messages = results.get('messages', [])
    emails = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['Subject', 'From', 'Date']).execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        from_ = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date_ = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        snippet = msg_data.get('snippet', '')
        emails.append({'subject': subject, 'from': from_, 'date': date_, 'snippet': snippet, 'id': msg['id']})
    logging.info(f"Fetched {len(emails)} unread emails from Gmail API.")
    return emails

if __name__ == '__main__':
    emails = fetch_unread_emails()
    for e in emails:
        print(f"Subject: {e['subject']}\nFrom: {e['from']}\nDate: {e['date']}\nSnippet: {e['snippet']}\n{'-'*40}")

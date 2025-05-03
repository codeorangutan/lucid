import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import logging
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from googleapiclient.errors import HttpError
from email_receiver import get_gmail_service, logger
from db import get_referrer_email_by_patient_id_yob

def send_pdf_via_email(pdf_path, recipient_email, subject=None, body=None):
    """
    Send a PDF file as an email attachment using Gmail API.
    Args:
        pdf_path (str): Path to the PDF file to send.
        recipient_email (str): Email address to send to.
        subject (str): Email subject (optional).
        body (str): Email body (optional).
    Raises:
        FileNotFoundError: If the PDF file does not exist.
        Exception: For Gmail API errors or send failures.
    """
    if not os.path.isfile(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    subject = subject or "Lucid Cognitive report is attached"
    body = body or "Please find your report attached. Patients Id number is in the name of the report."

    message = MIMEMultipart()
    message["to"] = recipient_email
    message["subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(pdf_path)}",
        )
        message.attach(part)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service = get_gmail_service()
    try:
        send_result = service.users().messages().send(
            userId="me", body={"raw": raw_message}
        ).execute()
        logger.info(f"Email sent to {recipient_email} with PDF {pdf_path}. Message ID: {send_result.get('id')}")
        return send_result
    except HttpError as error:
        logger.error(f"Failed to send email: {error}")
        raise

def get_recipient_email(patient_id=None, yob=None, email=None):
    """
    Determine recipient email from CLI args or DB lookup.
    Args:
        patient_id (str): Patient ID (id_number).
        yob (int): Year of birth (4 digits).
        email (str): Directly supplied email.
    Returns:
        str: Recipient email address.
    Raises:
        ValueError: If email cannot be determined.
    """
    if email:
        return email
    if patient_id and yob:
        return get_referrer_email_by_patient_id_yob(patient_id, yob)
    raise ValueError("Must supply either --email or both --patient-id and --yob.")

def main():
    parser = argparse.ArgumentParser(description="Send a PDF as an email attachment via Gmail.")
    parser.add_argument("--pdf", required=True, help="Path to PDF file to send.")
    parser.add_argument("--email", default=None, help="Recipient email address.")
    parser.add_argument("--patient-id", default=None, help="Patient ID (id_number) for DB lookup.")
    parser.add_argument("--yob", type=int, default=None, help="Year of birth (4 digits) for DB lookup.")
    parser.add_argument("--subject", default=None, help="Email subject (optional).")
    parser.add_argument("--body", default=None, help="Email body (optional).")
    args = parser.parse_args()
    try:
        recipient = get_recipient_email(args.patient_id, args.yob, args.email)
        send_pdf_via_email(args.pdf, recipient, args.subject, args.body)
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    main()

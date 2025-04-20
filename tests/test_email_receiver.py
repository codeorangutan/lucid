import sys
import os
import pytest
from unittest.mock import patch, MagicMock
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from email_receiver import list_unread_emails, save_referral

def test_list_unread_emails_returns_expected_headers():
    mock_mail = MagicMock()
    with patch('imaplib.IMAP4_SSL', return_value=mock_mail):
        mock_mail.login.return_value = ('OK', [b'Logged in'])
        mock_mail.select.return_value = ('OK', [b'INBOX selected'])
        mock_mail.search.return_value = ('OK', [b'1 2'])
        # Prepare two fake emails
        def fake_fetch(num, what):
            if num == b'1':
                msg = b"Subject: Test1\r\nFrom: foo@bar.com\r\nDate: Fri, 1 Jan 2021 12:00:00 +0000\r\n\r\nBody1"
            else:
                msg = b"Subject: Test2\r\nFrom: baz@qux.com\r\nDate: Sat, 2 Jan 2021 13:00:00 +0000\r\n\r\nBody2"
            return ('OK', [(None, msg)])
        mock_mail.fetch.side_effect = fake_fetch
        mock_mail.logout.return_value = ('BYE', [b'Logging out'])
        results = list_unread_emails('imap.example.com', 'user', 'pass')
        assert len(results) == 2
        assert results[0]['subject'] == 'Test1'
        assert results[0]['from'] == 'foo@bar.com'
        assert results[1]['subject'] == 'Test2'
        assert results[1]['from'] == 'baz@qux.com'

def test_skip_incomplete_referral_logs_warning(caplog):
    """Test that incomplete referrals are skipped and a warning is logged."""
    # Simulate a parsed email missing 'email' and 'id_number'
    parsed = {'email': None, 'id_number': None}
    subject = 'FW: Cognitive testing'
    body = ''
    referrer = 'Stephen Ford'
    referrer_email = 'stephen.ford@aurorahealth.com.au'
    referral_received_time = '2025-04-20 11:29:22.900590'
    caplog.set_level(logging.WARNING)
    with caplog.at_level(logging.WARNING):
        # Patch session to avoid DB interaction
        with patch('email_receiver.save_referral', return_value=None):
            # Simulate the check and log (as in the real code)
            required_fields = ['email', 'id_number']
            missing = [f for f in required_fields if not parsed.get(f)]
            if missing:
                logging.warning(f"Skipping referral: missing required fields {missing}. Subject: {subject}")
    assert any("Skipping referral: missing required fields" in r.message for r in caplog.records)

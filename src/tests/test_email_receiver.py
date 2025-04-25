import sys
import os
import pytest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from email_receiver import list_unread_emails

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

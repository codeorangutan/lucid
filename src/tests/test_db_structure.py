import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import pytest
from sqlalchemy import inspect
from db import engine, Referral

def test_referral_table_fields():
    inspector = inspect(engine)
    columns = inspector.get_columns('referrals')
    col_names = set(col['name'] for col in columns)
    expected_fields = {
        'id', 'email', 'mobile', 'dob', 'id_number', 'raw_subject', 'raw_body',
        'referral_received_time', 'test_request_time', 'referrer', 'referrer_email',
        'referral_confirmed_time', 'paid', 'invoice_date', 'invoice_number',
        'test_completed', 'retest', 'report_unprocessed', 'report_processed', 'report_sent_date'
    }
    assert expected_fields.issubset(col_names), f"Missing fields: {expected_fields - col_names}"
    # Optionally, print all fields for manual inspection
    print('Referral table fields:', col_names)

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import tempfile
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Base, Referral, save_referral
import orchestrator
from datetime import datetime, timedelta

@pytest.fixture
def test_db(monkeypatch):
    db_fd, db_path = tempfile.mkstemp()
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sessions = []
    def session_factory(*args, **kwargs):
        s = Session(*args, **kwargs)
        sessions.append(s)
        return s
    # Patch Session in all relevant modules (db, orchestrator, email_receiver, and all orchestrator pipeline stages)
    monkeypatch.setattr('db.Session', session_factory)
    monkeypatch.setattr('orchestrator.Session', session_factory, raising=False)
    monkeypatch.setattr('email_receiver.Session', session_factory, raising=False)
    try:
        import process_existing_reports
        monkeypatch.setattr('process_existing_reports.Session', session_factory, raising=False)
    except ImportError:
        pass
    monkeypatch.setattr('orchestrator.request_tests_for_pending_patients.Session', session_factory, raising=False)
    monkeypatch.setattr('orchestrator.enforce_safety_limits.Session', session_factory, raising=False)
    monkeypatch.setattr('orchestrator.send_reminders.Session', session_factory, raising=False)
    import builtins
    setattr(builtins, 'Session', session_factory)
    # Patch save_referral to always use the test session
    from db import save_referral as real_save_referral
    def test_save_referral(parsed, subject, body, referrer=None, referrer_email=None, referral_received_time=None, referral_confirmed_time=None):
        return real_save_referral(parsed, subject, body, referrer, referrer_email, referral_received_time, referral_confirmed_time, session=session_factory())
    monkeypatch.setattr('db.save_referral', test_save_referral)
    yield session_factory
    for s in sessions:
        s.close()
    engine.dispose()
    os.close(db_fd)
    os.remove(db_path)

def make_referral(email, id_number, subject, body, referrer, referrer_email, received_time):
    return {
        'email': email,
        'id_number': id_number,
        'subject': subject,
        'body': body,
        'referrer': referrer,
        'referrer_email': referrer_email,
        'referral_received_time': received_time
    }

def test_orchestrator_e2e_close_spaced_referrals_and_results(monkeypatch, test_db, caplog):
    now = datetime.now()
    referrals = [
        make_referral('user1@example.com', '111', 'Referral1', 'Body1', 'Dr. X', 'ref1@clinic.com', (now - timedelta(minutes=2)).isoformat()),
        make_referral('user2@example.com', '222', 'Referral2', 'Body2', 'Dr. Y', 'ref2@clinic.com', now.isoformat()),
    ]
    def fake_list_unread_emails_gmail_api(max_results=10):
        for r in referrals:
            save_referral(
                {'email': r['email'], 'mobile': '', 'dob': '', 'id_number': r['id_number']},
                r['subject'], r['body'], r['referrer'], r['referrer_email'], r['referral_received_time']
            )
        return referrals
    monkeypatch.setattr('email_receiver.list_unread_emails_gmail_api', fake_list_unread_emails_gmail_api, raising=False)
    monkeypatch.setattr('request_cns_test.request_tests_for_pending_patients', lambda headless=True: None, raising=False)
    # Patch monitor_cns_vs_notifications to accept any args/kwargs and return empty list
    monkeypatch.setattr('cns_vs_report_monitor.monitor_cns_vs_notifications', lambda *args, **kwargs: [], raising=False)
    monkeypatch.setattr('orchestrator.reformat_and_save_reports', lambda: None, raising=False)
    monkeypatch.setattr('orchestrator.send_reports_to_referrers', lambda: None, raising=False)
    monkeypatch.setattr('orchestrator.send_reminders', lambda: None, raising=False)
    monkeypatch.setattr('orchestrator.enforce_safety_limits', lambda: None, raising=False)

    orchestrator.main()

    session = test_db()
    all_referrals = session.query(Referral).all()
    print(f"DEBUG: Referrals in test DB: {all_referrals}")
    assert len(all_referrals) == 2
    emails = [r.email for r in all_referrals]
    assert 'user1@example.com' in emails
    assert 'user2@example.com' in emails
    assert any('Processing new referrals' in r.message for r in caplog.records)
    assert any('Enforcing safety limits' in r.message for r in caplog.records)

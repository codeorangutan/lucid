"""
Test for new patient model logic: get_or_create_patient and insert_cognitive_scores with patient_fk_id.
This test uses the main database, but cleans up after itself.
"""
import sys
import os
import random
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from db import get_session, get_or_create_patient, insert_cognitive_scores, CognitiveScore
from sqlalchemy import text  # Ensure compatibility with SQLAlchemy 1.4+

TEST_PATIENT_ID = f"test_patient_{random.randint(10000,99999)}"
TEST_YOB = 1980
TEST_REFERRAL_ID = 999999
TEST_NAME = "Test Patient Cascade"

TEST_SESSION_ID = 99999999

# 1. Create or get patient
with get_session() as session:
    print("Creating/finding patient...")
    patient_fk_id = get_or_create_patient(session, TEST_PATIENT_ID, TEST_YOB, TEST_REFERRAL_ID, TEST_NAME)
    print(f"Got patient_fk_id: {patient_fk_id}")

# 2. Insert cognitive score with both legacy and new keys
score_data = [{
    'patient_id': TEST_PATIENT_ID,
    'domain': 'TestDomain',
    'patient_score': '99',
    'standard_score': '100',
    'percentile': '99',
    'validity_index': 'valid',
}]

print("Inserting cognitive score with patient_fk_id...")
inserted = insert_cognitive_scores(TEST_SESSION_ID, score_data, patient_fk_id=patient_fk_id)
print(f"Inserted {inserted} cognitive score(s)")

# 3. Query and print for validation
with get_session() as session:
    result = session.query(CognitiveScore).filter_by(session_id=TEST_SESSION_ID, patient_fk_id=patient_fk_id).first()
    print("Queried inserted record:")
    if result:
        print(f"  session_id: {result.session_id}\n  patient_id: {result.patient_id}\n  patient_fk_id: {result.patient_fk_id}\n  domain: {result.domain}\n  patient_score: {result.patient_score}")
    else:
        print("  No record found!")

# 4. Clean up test data
with get_session() as session:
    deleted = session.query(CognitiveScore).filter_by(session_id=TEST_SESSION_ID, patient_fk_id=patient_fk_id).delete()
    # Robust cleanup using SQLAlchemy text()
    session.execute(text("DELETE FROM patients WHERE system_patient_id = :pid"), {"pid": patient_fk_id})
    session.commit()
    print(f"Cleaned up {deleted} cognitive score(s) and patient {patient_fk_id}")

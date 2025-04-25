"""
Test script to initialize the database, add a Referral with a PDF path, and set flags for orchestrator parse/upload cycle.
Run this after deleting your DBs and placing a test PDF in your reports directory.
"""
import os
from datetime import datetime
from db import Session, Referral, Base, create_engine

def init_db(db_url=None):
    # Use default DB URL from db.py if not provided
    if db_url is None:
        db_url = os.environ.get('DATABASE_URL', 'sqlite:///lucid.data')
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine

def create_test_referral(pdf_path, patient_id="TEST123", email="test@example.com"):
    with Session() as session:
        referral = Referral(
            email=email,
            id_number=patient_id,
            pdf_path=pdf_path,
            report_unprocessed=True,
            report_processed=False,
            test_completed=True,
            referral_received_time=datetime.now(),
        )
        session.add(referral)
        session.commit()
        print(f"Test referral created with id: {referral.id}, pdf_path: {pdf_path}")
        return referral

def main():
    # --- USER: Set this path to your test PDF ---
    test_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../reports/test_report.pdf'))
    if not os.path.exists(test_pdf_path):
        raise FileNotFoundError(f"Test PDF not found at {test_pdf_path}. Please copy a test PDF there.")
    engine = init_db()
    create_test_referral(test_pdf_path)

if __name__ == "__main__":
    main()

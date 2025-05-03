from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from datetime import datetime

# Use unencrypted SQLite for development
DB_FILENAME = 'lucid_data.db'
DATABASE_URL = f'sqlite:///{DB_FILENAME}'

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={'check_same_thread': False}
)
Base = declarative_base()

class Referral(Base):
    __tablename__ = 'referrals'
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    mobile = Column(String)
    dob = Column(String)
    id_number = Column(String)
    raw_subject = Column(String)
    raw_body = Column(String)
    referral_received_time = Column(DateTime)
    test_request_time = Column(DateTime)
    referrer = Column(String)
    referrer_email = Column(String)
    referral_confirmed_time = Column(DateTime)
    paid = Column(Boolean, default=False)
    invoice_date = Column(DateTime)
    invoice_number = Column(String)
    test_completed = Column(Boolean, default=False)
    retest = Column(Boolean, default=False)
    report_unprocessed = Column(Boolean, default=True)
    report_processed = Column(Boolean, default=False)
    report_sent_date = Column(DateTime)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def save_referral(parsed, subject, body, referrer=None, referrer_email=None, referral_received_time=None, referral_confirmed_time=None):
    with Session() as session:
        referral = Referral(
            email=parsed['email'],
            mobile=parsed['mobile'],
            dob=parsed['dob'],
            id_number=parsed['id_number'],
            raw_subject=subject,
            raw_body=body,
            referral_received_time=referral_received_time,
            referrer=referrer,
            referrer_email=referrer_email,
            referral_confirmed_time=referral_confirmed_time
        )
        session.add(referral)
        session.commit()

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
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
    test_resent = Column(Boolean, default=False)
    test_resent_time = Column(DateTime, nullable=True)
    pdf_path = Column(String)

class TestSession(Base):
    __tablename__ = 'test_sessions'
    id = Column(Integer, primary_key=True)
    referral_id = Column(Integer, nullable=True)
    session_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='pending')

# --- Cognitive Score Model ---
class CognitiveScore(Base):
    __tablename__ = 'cognitive_scores'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    domain = Column(String, nullable=False)
    patient_score = Column(String)
    standard_score = Column(String)
    percentile = Column(String)
    validity_index = Column(String)

# --- Subtest Result Model ---
class SubtestResult(Base):
    __tablename__ = 'subtest_results'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    subtest_name = Column(String, nullable=False)
    metric = Column(String, nullable=False)
    score = Column(Float)
    standard_score = Column(Float)
    percentile = Column(Float)
    validity_flag = Column(Boolean, default=True)

# --- ASRS Response Model ---
class ASRSResponse(Base):
    __tablename__ = 'asrs_responses'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    question_number = Column(Integer, nullable=False)
    part = Column(String, nullable=True)
    response = Column(String, nullable=False)

# --- DSM Diagnosis Model ---
class DSMDiagnosis(Base):
    __tablename__ = 'dsm_diagnoses'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    diagnosis = Column(String, nullable=False)
    code = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    notes = Column(String, nullable=True)

# --- DSM Criteria Met Model ---
class DSMCriteriaMet(Base):
    __tablename__ = 'dsm_criteria_met'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    dsm_criterion = Column(String, nullable=False)
    dsm_category = Column(String, nullable=False)
    is_met = Column(Boolean, nullable=False)

# --- Epworth Response Model ---
class EpworthResponse(Base):
    __tablename__ = 'epworth_responses'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    situation = Column(String, nullable=False)
    score = Column(Integer, nullable=False)

# --- Epworth Summary Model ---
class EpworthSummary(Base):
    __tablename__ = 'epworth_summary'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    total_score = Column(Integer, nullable=False)
    interpretation = Column(String, nullable=True)

# --- NPQ Domain Score Model ---
class NPQDomainScore(Base):
    __tablename__ = 'npq_domain_scores'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    domain = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)

# --- NPQ Response Model ---
class NPQResponse(Base):
    __tablename__ = 'npq_responses'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    patient_id = Column(String)  # Unique patient identifier from PDF
    domain = Column(String, nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# --- Save Referral ---
def save_referral(parsed, subject, body, referrer=None, referrer_email=None, referral_received_time=None, referral_confirmed_time=None):
    """
    Save a new referral to the database.
    Returns the referral ID.
    """
    with Session() as session:
        referral = Referral(
            email=parsed.get('email', ''),
            mobile=parsed.get('mobile', ''),
            dob=parsed.get('dob', ''),
            id_number=parsed.get('id_number', ''),
            raw_subject=subject,
            raw_body=body,
            referral_received_time=referral_received_time,
            referral_confirmed_time=referral_confirmed_time,
            referrer=referrer,
            referrer_email=referrer_email,
        )
        session.add(referral)
        session.commit()
        return referral.id

# --- Test Session Creation ---
def create_test_session(referral_id, session_date, status="pending"):
    with Session() as session:
        test_session = TestSession(
            referral_id=referral_id,
            session_date=session_date,
            status=status
        )
        session.add(test_session)
        session.commit()
        return test_session.id

# --- Cognitive Score Insert ---
def insert_cognitive_scores(session_id, scores):
    def clean(val):
        if val is None:
            return None
        try:
            return float(val)
        except Exception:
            return val
    with Session() as session:
        records = [
            CognitiveScore(
                session_id=session_id,
                patient_id=score.get('patient_id'),  # Add patient_id
                domain=score['domain'],
                patient_score=clean(score.get('patient_score')),
                standard_score=clean(score.get('standard_score')),
                percentile=clean(score.get('percentile')),
                validity_index=score.get('validity_index'),
            )
            for score in scores
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- Subtest Result Insert ---
def insert_subtest_results(session_id, subtests):
    with Session() as session:
        records = [
            SubtestResult(
                session_id=session_id,
                patient_id=s['patient_id'],  # Add patient_id
                subtest_name=s['subtest_name'],
                metric=s['metric'],
                score=s.get('score'),
                standard_score=s.get('standard_score'),
                percentile=s.get('percentile'),
                validity_flag=s.get('validity_flag', True),
            )
            for s in subtests
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- ASRS Response Insert ---
def insert_asrs_responses(session_id, responses):
    with Session() as session:
        records = [
            ASRSResponse(
                session_id=session_id,
                patient_id=resp.get('patient_id'),  # Add patient_id
                question_number=resp['question_number'],
                part=resp.get('part'),
                response=resp['response'],
            )
            for resp in responses
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- DSM Diagnosis Insert ---
def insert_dsm_diagnosis(session_id, diagnoses):
    with Session() as session:
        records = [
            DSMDiagnosis(
                session_id=session_id,
                patient_id=diag.get('patient_id'),  # Add patient_id
                diagnosis=diag['diagnosis'],
                code=diag.get('code'),
                severity=diag.get('severity'),
                notes=diag.get('notes'),
            )
            for diag in diagnoses
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- Insert DSM Criteria Met ---
def insert_dsm_criteria_met(session_id, criteria_data):
    with Session() as session:
        records = [
            DSMCriteriaMet(
                session_id=session_id,
                patient_id=item.get('patient_id'),  # Add patient_id
                dsm_criterion=item['dsm_criterion'],
                dsm_category=item['dsm_category'],
                is_met=bool(item['is_met']),
            )
            for item in criteria_data
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- Insert Epworth Responses ---
def insert_epworth_responses(session_id, responses):
    with Session() as session:
        records = [
            EpworthResponse(
                session_id=session_id,
                patient_id=resp.get('patient_id'),  # Add patient_id
                situation=resp['situation'],
                score=resp['score'],
            )
            for resp in responses
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- Insert Epworth Summary ---
def insert_epworth_summary(session_id, summary):
    with Session() as session:
        record = EpworthSummary(
            session_id=session_id,
            patient_id=summary.get('patient_id'),  # Add patient_id
            total_score=summary['total_score'],
            interpretation=summary.get('interpretation'),
        )
        session.add(record)
        session.commit()
        return 1

# --- Insert NPQ Domain Scores ---
def insert_npq_domain_scores(session_id, scores):
    with Session() as session:
        records = [
            NPQDomainScore(
                session_id=session_id,
                patient_id=score.get('patient_id'),  # Add patient_id
                domain=score['domain'],
                score=score['score'],
                severity=score['severity'],
            )
            for score in scores
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- Insert NPQ Responses ---
def insert_npq_responses(session_id, responses):
    with Session() as session:
        records = [
            NPQResponse(
                session_id=session_id,
                patient_id=resp.get('patient_id'),  # Add patient_id
                domain=resp['domain'],
                question_number=resp['question_number'],
                question_text=resp['question_text'],
                score=resp['score'],
                severity=resp['severity'],
            )
            for resp in responses
        ]
        session.add_all(records)
        session.commit()
        return len(records)

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
    question_number = Column(Integer, nullable=False)
    part = Column(String, nullable=True)
    response = Column(String, nullable=False)

# --- DSM Diagnosis Model ---
class DSMDiagnosis(Base):
    __tablename__ = 'dsm_diagnoses'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    diagnosis = Column(String, nullable=False)
    code = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    notes = Column(String, nullable=True)

# --- DSM Criteria Met Model ---
class DSMCriteriaMet(Base):
    __tablename__ = 'dsm_criteria_met'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    dsm_criterion = Column(String, nullable=False)
    dsm_category = Column(String, nullable=False)
    is_met = Column(Boolean, nullable=False)

# --- Epworth Response Model ---
class EpworthResponse(Base):
    __tablename__ = 'epworth_responses'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    situation = Column(String, nullable=False)
    score = Column(Integer, nullable=False)

# --- Epworth Summary Model ---
class EpworthSummary(Base):
    __tablename__ = 'epworth_summary'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    total_score = Column(Integer, nullable=False)
    interpretation = Column(String, nullable=True)

# --- NPQ Domain Score Model ---
class NPQDomainScore(Base):
    __tablename__ = 'npq_domain_scores'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    domain = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)

# --- NPQ Response Model ---
class NPQResponse(Base):
    __tablename__ = 'npq_responses'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    domain = Column(String, nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)

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

def create_test_session(referral_id=None, session_date=None, status="pending"):
    """
    Create a new test session record and return its ID.
    Args:
        referral_id (int, optional): Link to Referral if available.
        session_date (datetime, optional): Date/time of session. Defaults to now.
        status (str, optional): Status string. Defaults to 'pending'.
    Returns:
        int: The ID of the new session.
    """
    with Session() as session:
        new_session = TestSession(
            referral_id=referral_id,
            session_date=session_date or datetime.utcnow(),
            status=status
        )
        session.add(new_session)
        session.commit()
        return new_session.id

# --- Utility: Safe conversion for numeric fields (copied from parsing_helpers) ---
def safe_float(val):
    try:
        if val is None:
            return None
        val = str(val).strip()
        if val.upper() in ("NA", "N/A", "--", ""):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None

# --- Insert Cognitive Scores (with sanitization) ---
def insert_cognitive_scores(session_id, scores):
    """
    Insert cognitive scores for a session. Passes values as-is (except for patient_score, standard_score, percentile: convert NA/empty to None, else string/number as-is).
    Args:
        session_id (int): ID of the test session.
        scores (list of dict): Each dict should have keys: domain, patient_score, standard_score, percentile, validity_index.
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        def clean(val):
            # Only convert NA/empty to None, else pass as string or number as-is
            if val is None:
                return None
            if isinstance(val, str) and val.strip().upper() in ("NA", "N/A", "--", ""):
                return None
            return val
        records = [
            CognitiveScore(
                session_id=session_id,
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

# --- Insert Subtest Results ---
def insert_subtest_results(session_id, subtests):
    """
    Insert subtest results for a session.
    Args:
        session_id (int): ID of the test session.
        subtests (list of dict): Each dict should have keys: subtest_name, metric, score, standard_score, percentile, validity_flag (optional).
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        records = [
            SubtestResult(
                session_id=session_id,
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

# --- Insert ASRS Responses ---
def insert_asrs_responses(session_id, responses):
    """
    Insert ASRS responses for a session.
    Args:
        session_id (int): ID of the test session.
        responses (list of dict): Each dict should have keys: question_number, part, response.
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        records = [
            ASRSResponse(
                session_id=session_id,
                question_number=resp['question_number'],
                part=resp.get('part'),
                response=resp['response'],
            )
            for resp in responses
        ]
        session.add_all(records)
        session.commit()
        return len(records)

# --- Insert DSM Diagnoses ---
def insert_dsm_diagnosis(session_id, diagnoses):
    """
    Insert DSM diagnoses for a session.
    Args:
        session_id (int): ID of the test session.
        diagnoses (list of dict): Each dict should have keys: diagnosis, code (optional), severity (optional), notes (optional).
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        records = [
            DSMDiagnosis(
                session_id=session_id,
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
    """
    Insert DSM criteria met for a session.
    Args:
        session_id (int): ID of the test session.
        criteria_data (list of dict): Each dict should have keys: dsm_criterion, dsm_category, is_met (bool).
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        records = [
            DSMCriteriaMet(
                session_id=session_id,
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
    """
    Insert Epworth responses for a session.
    Args:
        session_id (int): ID of the test session.
        responses (list of dict): Each dict should have keys: situation, score.
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        records = [
            EpworthResponse(
                session_id=session_id,
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
    """
    Insert Epworth summary for a session.
    Args:
        session_id (int): ID of the test session.
        summary (dict): Should have keys: total_score (int), interpretation (str, optional).
    Returns:
        int: 1 if inserted successfully.
    """
    with Session() as session:
        record = EpworthSummary(
            session_id=session_id,
            total_score=summary['total_score'],
            interpretation=summary.get('interpretation'),
        )
        session.add(record)
        session.commit()
        return 1

# --- Insert NPQ Domain Scores ---
def insert_npq_domain_scores(session_id, scores):
    """
    Insert NPQ domain scores for a session.
    Args:
        session_id (int): ID of the test session.
        scores (list of dict): Each dict should have keys: domain, score, severity.
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        records = [
            NPQDomainScore(
                session_id=session_id,
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
    """
    Insert NPQ responses for a session.
    Args:
        session_id (int): ID of the test session.
        responses (list of dict): Each dict should have keys: domain, question_number, question_text, score, severity.
    Returns:
        int: Number of records inserted.
    """
    with Session() as session:
        records = [
            NPQResponse(
                session_id=session_id,
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

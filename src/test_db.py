import pytest
from db import insert_cognitive_scores, create_test_session, Session, CognitiveScore, insert_subtest_results, SubtestResult, insert_asrs_responses, ASRSResponse, insert_dsm_diagnosis, DSMDiagnosis, insert_epworth_responses, EpworthResponse, NPQDomainScore, NPQResponse, insert_npq_domain_scores, insert_npq_responses, insert_dsm_criteria_met, DSMCriteriaMet, insert_epworth_summary, EpworthSummary

def test_insert_cognitive_scores():
    # Create a test session
    session_id = create_test_session()
    scores = [
        {
            'domain': 'Verbal Memory',
            'patient_score': 42.0,
            'standard_score': 100.0,
            'percentile': 50.0,
            'validity_index': 1.0
        },
        {
            'domain': 'Visual Memory',
            'patient_score': 45.0,
            'standard_score': 105.0,
            'percentile': 55.0,
            'validity_index': 1.0
        },
    ]
    count = insert_cognitive_scores(session_id, scores)
    assert count == 2

    # Verify in DB
    with Session() as session:
        db_scores = session.query(CognitiveScore).filter_by(session_id=session_id).all()
        assert len(db_scores) == 2
        assert db_scores[0].domain == 'Verbal Memory'
        assert db_scores[1].domain == 'Visual Memory'

def test_insert_subtest_results():
    # Create a test session
    session_id = create_test_session()
    subtests = [
        {
            'subtest_name': 'Stroop Test',
            'metric': 'Reaction Time',
            'score': 250.5,
            'standard_score': 98.0,
            'percentile': 48.0,
            'validity_flag': True
        },
        {
            'subtest_name': 'Symbol Digit Coding',
            'metric': 'Correct Responses',
            'score': 80.0,
            'standard_score': 102.0,
            'percentile': 60.0
            # validity_flag omitted (should default to True)
        },
    ]
    count = insert_subtest_results(session_id, subtests)
    assert count == 2

    # Verify in DB
    with Session() as session:
        db_subtests = session.query(SubtestResult).filter_by(session_id=session_id).all()
        assert len(db_subtests) == 2
        assert db_subtests[0].subtest_name == 'Stroop Test'
        assert db_subtests[1].subtest_name == 'Symbol Digit Coding'
        assert db_subtests[1].validity_flag is True

def test_insert_asrs_responses():
    # Create a test session
    session_id = create_test_session()
    responses = [
        {
            'question_number': 1,
            'part': 'A',
            'response': 'Never'
        },
        {
            'question_number': 2,
            'part': 'B',
            'response': 'Sometimes'
        },
        {
            'question_number': 3,
            # part omitted (should be None)
            'response': 'Often'
        },
    ]
    count = insert_asrs_responses(session_id, responses)
    assert count == 3

    # Verify in DB
    with Session() as session:
        db_responses = session.query(ASRSResponse).filter_by(session_id=session_id).all()
        assert len(db_responses) == 3
        assert db_responses[0].question_number == 1
        assert db_responses[0].part == 'A'
        assert db_responses[1].question_number == 2
        assert db_responses[1].part == 'B'
        assert db_responses[2].question_number == 3
        assert db_responses[2].part is None
        assert db_responses[2].response == 'Often'

def test_insert_dsm_diagnosis():
    # Create a test session
    session_id = create_test_session()
    diagnoses = [
        {
            'diagnosis': 'ADHD, Combined Type',
            'code': 'F90.2',
            'severity': 'moderate',
            'notes': 'Symptoms present in multiple settings.'
        },
        {
            'diagnosis': 'Generalized Anxiety Disorder',
            # code omitted
            'severity': 'mild',
            # notes omitted
        },
    ]
    count = insert_dsm_diagnosis(session_id, diagnoses)
    assert count == 2

    # Verify in DB
    with Session() as session:
        db_diags = session.query(DSMDiagnosis).filter_by(session_id=session_id).all()
        assert len(db_diags) == 2
        assert db_diags[0].diagnosis == 'ADHD, Combined Type'
        assert db_diags[0].code == 'F90.2'
        assert db_diags[0].severity == 'moderate'
        assert db_diags[0].notes == 'Symptoms present in multiple settings.'
        assert db_diags[1].diagnosis == 'Generalized Anxiety Disorder'
        assert db_diags[1].code is None
        assert db_diags[1].severity == 'mild'
        assert db_diags[1].notes is None

def test_insert_dsm_criteria_met():
    # Create a test session
    session_id = create_test_session()
    criteria_data = [
        {'dsm_criterion': 'A1', 'dsm_category': 'Inattentive', 'is_met': True},
        {'dsm_criterion': 'A2', 'dsm_category': 'Hyperactive', 'is_met': False},
    ]
    count = insert_dsm_criteria_met(session_id, criteria_data)
    assert count == 2
    with Session() as session:
        db_criteria = session.query(DSMCriteriaMet).filter_by(session_id=session_id).all()
        assert len(db_criteria) == 2
        assert db_criteria[0].dsm_criterion == 'A1'
        assert db_criteria[0].dsm_category == 'Inattentive'
        assert db_criteria[0].is_met is True
        assert db_criteria[1].dsm_criterion == 'A2'
        assert db_criteria[1].dsm_category == 'Hyperactive'
        assert db_criteria[1].is_met is False

def test_insert_epworth_responses():
    # Create a test session
    session_id = create_test_session()
    responses = [
        {
            'situation': 'Sitting and reading',
            'score': 1
        },
        {
            'situation': 'Watching TV',
            'score': 2
        },
        {
            'situation': 'Sitting inactive in a public place',
            'score': 0
        },
    ]
    count = insert_epworth_responses(session_id, responses)
    assert count == 3

    # Verify in DB
    with Session() as session:
        db_responses = session.query(EpworthResponse).filter_by(session_id=session_id).all()
        assert len(db_responses) == 3
        assert db_responses[0].situation == 'Sitting and reading'
        assert db_responses[0].score == 1
        assert db_responses[1].situation == 'Watching TV'
        assert db_responses[1].score == 2
        assert db_responses[2].situation == 'Sitting inactive in a public place'
        assert db_responses[2].score == 0

def test_insert_npq_domain_scores():
    # Create a test session
    session_id = create_test_session()
    scores = [
        {'domain': 'Attention', 'score': 18, 'severity': 'moderate'},
        {'domain': 'Memory', 'score': 22, 'severity': 'severe'},
    ]
    count = insert_npq_domain_scores(session_id, scores)
    assert count == 2
    with Session() as session:
        db_scores = session.query(NPQDomainScore).filter_by(session_id=session_id).all()
        assert len(db_scores) == 2
        assert db_scores[0].domain == 'Attention'
        assert db_scores[0].score == 18
        assert db_scores[0].severity == 'moderate'
        assert db_scores[1].domain == 'Memory'
        assert db_scores[1].score == 22
        assert db_scores[1].severity == 'severe'

def test_insert_npq_responses():
    # Create a test session
    session_id = create_test_session()
    responses = [
        {'domain': 'Attention', 'question_number': 1, 'question_text': 'I have trouble focusing.', 'score': 2, 'severity': 'moderate'},
        {'domain': 'Memory', 'question_number': 2, 'question_text': 'I forget appointments.', 'score': 3, 'severity': 'severe'},
    ]
    count = insert_npq_responses(session_id, responses)
    assert count == 2
    with Session() as session:
        db_responses = session.query(NPQResponse).filter_by(session_id=session_id).all()
        assert len(db_responses) == 2
        assert db_responses[0].domain == 'Attention'
        assert db_responses[0].question_number == 1
        assert db_responses[0].question_text == 'I have trouble focusing.'
        assert db_responses[0].score == 2
        assert db_responses[0].severity == 'moderate'
        assert db_responses[1].domain == 'Memory'
        assert db_responses[1].question_number == 2
        assert db_responses[1].question_text == 'I forget appointments.'
        assert db_responses[1].score == 3
        assert db_responses[1].severity == 'severe'

def test_insert_epworth_summary():
    # Create a test session
    session_id = create_test_session()
    summary = {'total_score': 12, 'interpretation': 'Mild sleepiness'}
    count = insert_epworth_summary(session_id, summary)
    assert count == 1
    with Session() as session:
        db_summary = session.query(EpworthSummary).filter_by(session_id=session_id).first()
        assert db_summary is not None
        assert db_summary.total_score == 12
        assert db_summary.interpretation == 'Mild sleepiness'

if __name__ == "__main__":
    pytest.main([__file__])

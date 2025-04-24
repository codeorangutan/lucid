def import_pdf_to_db(pdf_path):
    """
    Parses a cognitive report PDF using parsing_helpers and imports the data into the unified SQLAlchemy database.
    Returns True on success, False on failure.
    """
    logger.info(f"Attempting to import PDF data for: {pdf_path}")

    # --- Stage 1: Extract text blocks ---
    lines = extract_text_blocks(pdf_path)
    if not lines:
        logger.error(f"Could not extract any text blocks from {pdf_path}.")
        return False
    raw_text = "\n".join(lines)
    
    # --- Stage 2: Parse Patient Info ---
    patient_info_tuple = parse_basic_info(raw_text)
    if not patient_info_tuple or not patient_info_tuple[0]:
        logger.error(f"Essential patient information (ID) could not be parsed from {pdf_path}.")
        return False
    patient_id, test_date, age, language = patient_info_tuple
    patient_info = {
        'patient_id': patient_id,
        'test_date': test_date,
        'age': age,
        'language': language
    }

    # --- Stage 3: Referral/Session Setup (unchanged) ---
    referral_id = patient_info.get('referral_id')
    if not referral_id:
        from db import Session, Referral
        with Session() as session:
            referral = session.query(Referral).filter_by(id_number=patient_info.get('patient_id')).first()
            if referral:
                referral_id = referral.id
            else:
                from datetime import datetime
                from db import save_referral
                referral_id = save_referral(
                    {'email': patient_info.get('email', ''),
                     'mobile': patient_info.get('mobile', ''),
                     'dob': patient_info.get('dob', ''),
                     'id_number': patient_info.get('patient_id', '')},
                    subject='[Auto-imported]',
                    body='',
                    referrer=None,
                    referrer_email=None,
                    referral_received_time=datetime.now(),
                    referral_confirmed_time=None
                )
    session_date = patient_info.get('test_date')
    from datetime import datetime
    if isinstance(session_date, str):
        try:
            session_date = datetime.strptime(session_date, '%B %d, %Y %H:%M:%S')
        except Exception:
            try:
                session_date = datetime.strptime(session_date, '%Y-%m-%d %H:%M:%S')
            except Exception:
                session_date = datetime.now()
    elif session_date is None:
        session_date = datetime.now()
    session_id = create_test_session(referral_id, session_date, status="parsed")

    # --- Stage 4: Parse and Insert Data ---
    # Cognitive Scores
    raw_score_tuples = parse_cognitive_scores(raw_text, patient_id)
    # Convert tuples to dicts, sanitize only numeric fields
    raw_score_dicts = [
        {
            'domain': t[1],
            'patient_score': safe_float(t[2]),
            'standard_score': safe_float(t[3]),
            'percentile': safe_float(t[4]),
            'validity_index': t[5] if len(t) > 5 else None,
            'patient_id': patient_id  # <-- Add patient_id to dict
        }
        for t in raw_score_tuples
    ]
    insert_cognitive_scores(session_id, raw_score_dicts)

    # Epworth
    epworth_total, epworth_responses = parse_epworth(raw_text, patient_id)
    # Convert tuples to dicts for DB insert
    epworth_response_dicts = [
        {'situation': t[2], 'score': t[3], 'patient_id': patient_id} for t in epworth_responses
    ]
    insert_epworth_responses(session_id, epworth_response_dicts)
    if epworth_total is not None:
        insert_epworth_summary(session_id, {'total_score': epworth_total, 'patient_id': patient_id})

    # Subtests
    logger.info(f"Parsing cognitive subtests from PDF: {pdf_path}")
    subtest_tuples = parse_all_subtests(pdf_path, patient_id)
    subtest_dicts = [
        {
            'subtest_name': t[1],
            'metric': t[2],
            'score': t[3],
            'standard_score': t[4],
            'percentile': t[5],
            'validity_flag': t[6] if len(t) > 6 else True,
            'patient_id': patient_id  # <-- Add patient_id to dict
        }
        for t in subtest_tuples
    ]
    insert_subtest_results(session_id, subtest_dicts)

    # ASRS
    asrs_tuples = parse_asrs_with_bounding_boxes(pdf_path, patient_id)
    asrs_dicts = [
        {
            'question_number': t[1],
            'part': t[2],
            'response': t[3],
            'patient_id': patient_id
        }
        for t in asrs_tuples
    ]
    insert_asrs_responses(session_id, asrs_dicts)

    # NPQ
    npq_pages = find_npq_pages(pdf_path)
    npq_questions = []
    npq_domain_scores = []
    if npq_pages:
        npq_questions = extract_npq_questions_pymupdf(pdf_path, npq_pages)
        npq_questions = [
            {
                'question_number': t[0],
                'question_text': t[1],
                'score': t[2],
                'severity': t[3],
                'domain': t[4] if len(t) > 4 else None,
                'patient_id': patient_id
            }
            for t in npq_questions
        ]
        npq_domain_scores = extract_npq_domain_scores_from_pdf(pdf_path, npq_pages)
        npq_domain_scores = [
            {
                'domain': t[0],
                'score': t[1],
                'severity': t[2],
                'patient_id': patient_id
            }
            for t in npq_domain_scores
        ]
    insert_npq_responses(session_id, npq_questions)
    insert_npq_domain_scores(session_id, npq_domain_scores)

    # DSM
    dsm = extract_dsm_diagnosis(asrs_dicts, patient_id)
    if dsm:
        for d in dsm:
            d['patient_id'] = patient_id
        insert_dsm_diagnosis(session_id, dsm)
    criteria_data = extract_dsm_criteria(asrs_dicts, patient_id)
    if criteria_data:
        for c in criteria_data:
            c['patient_id'] = patient_id
        insert_dsm_criteria_met(session_id, criteria_data)

    logger.info(f"Successfully imported all available data for session ID: {session_id}")
    return True

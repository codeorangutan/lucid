import logging

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("importer.log", mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__) 
logger.info("Logging initialized: starting cognitive_importer.py")

# ... (file truncated for brevity) ...
    if npq_pages:
        npq_questions = extract_npq_questions_pymupdf(pdf_path, npq_pages)
        npq_questions = [
            {
                'question_number': t[0],
                'question_text': t[1],
                'score': t[2],
                'severity': t[3],
                'domain': t[4] if len(t) > 4 else None
            }
            for t in npq_questions
        ]
        npq_domain_scores = extract_npq_domain_scores_from_pdf(pdf_path, npq_pages)
        # Convert tuples to dicts for DB insertion
        npq_domain_scores = [
            {'domain': t[0], 'score': t[1], 'severity': t[2]}
            for t in npq_domain_scores
        ]
    else:
        npq_section_text = '\n'.join([lines[i] for i in npq_pages]) if npq_pages else raw_text
        npq_questions = parse_npq_questions_from_text(npq_section_text)
        npq_questions = [
            {
                'question_number': t[0],
                'question_text': t[1],
                'score': t[2],
                'severity': t[3],
                'domain': None
            }
            for t in npq_questions
        ]
    insert_npq_responses(session_id, npq_questions)
    insert_npq_domain_scores(session_id, npq_domain_scores)
# ... (file truncated for brevity) ...

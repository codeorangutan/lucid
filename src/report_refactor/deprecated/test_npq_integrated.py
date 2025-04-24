import sqlite3
import os
import sys
from cognitive_importer import extract_and_insert_npq_questions, extract_npq_table

def test_npq_extraction(pdf_path):
    """Test NPQ extraction and insertion"""
    # Create a test database connection
    conn = sqlite3.connect('cognitive_analysis.db')
    
    try:
        # Clear existing data for test patient
        patient_id = "40277"
        cursor = conn.cursor()
        cursor.execute('DELETE FROM npq_questions WHERE patient_id=?', (patient_id,))
        cursor.execute('DELETE FROM npq_scores WHERE patient_id=?', (patient_id,))
        conn.commit()
        print(f"Cleared existing NPQ data for patient {patient_id}")
        
        # Extract and insert NPQ questions
        print("\n--- Testing NPQ Questions Extraction ---")
        npq_success = extract_and_insert_npq_questions(pdf_path, patient_id, conn)
        print(f"NPQ Questions extraction success: {npq_success}")
        
        # Extract and insert NPQ domain scores
        print("\n--- Testing NPQ Domain Scores Extraction ---")
        domain_data, _ = extract_npq_table(pdf_path)
        
        # Convert domain_data to the expected format for npq_scores
        npq_scores = []
        for domain, score, severity in domain_data:
            npq_scores.append((patient_id, domain, score, severity, ""))
        
        if npq_scores:
            print(f"Inserting {len(npq_scores)} NPQ domain scores")
            conn.executemany("INSERT INTO npq_scores (patient_id, domain, score, severity, description) VALUES (?, ?, ?, ?, ?)", npq_scores)
            print(f"Successfully inserted {len(npq_scores)} NPQ domain scores")
        else:
            print("No NPQ domain scores found")
        
        # Verify data in database
        print("\n--- Verification ---")
        cursor.execute('SELECT COUNT(*) FROM npq_questions WHERE patient_id=?', (patient_id,))
        question_count = cursor.fetchone()[0]
        print(f"NPQ questions in database: {question_count}")
        
        cursor.execute('SELECT COUNT(*) FROM npq_scores WHERE patient_id=?', (patient_id,))
        score_count = cursor.fetchone()[0]
        print(f"NPQ domain scores in database: {score_count}")
        
        conn.commit()
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "g:\\My Drive\\Programming\\Report_Reformat\\SQL_Data Extractor_from_PDF\\40277.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    test_npq_extraction(pdf_path)

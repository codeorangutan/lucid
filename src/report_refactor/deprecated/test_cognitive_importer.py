import sqlite3
import os
import sys
from cognitive_importer import find_npq_pages, extract_npq_questions_pymupdf, insert_npq_questions, extract_npq_table

def test_npq_extraction(pdf_path, patient_id="40277"):
    """Test NPQ extraction and insertion"""
    # Create a test database connection
    conn = sqlite3.connect('cognitive_analysis.db')
    
    try:
        # Clear existing data for test patient
        cursor = conn.cursor()
        cursor.execute('DELETE FROM npq_questions WHERE patient_id=?', (patient_id,))
        cursor.execute('DELETE FROM npq_scores WHERE patient_id=?', (patient_id,))
        conn.commit()
        print(f"Cleared existing NPQ data for patient {patient_id}")
        
        # Step 1: Find NPQ pages
        print("\n--- Finding NPQ Pages ---")
        npq_pages = find_npq_pages(pdf_path)
        if not npq_pages:
            print("No NPQ pages found in PDF")
            return False
        
        # Step 2: Extract NPQ questions
        print("\n--- Extracting NPQ Questions ---")
        question_data = extract_npq_questions_pymupdf(pdf_path, npq_pages)
        if not question_data:
            print("No NPQ questions extracted")
            return False
        
        # Step 3: Insert NPQ questions
        print("\n--- Inserting NPQ Questions ---")
        insert_count = insert_npq_questions(conn, patient_id, question_data)
        print(f"Inserted {insert_count} NPQ questions")
        
        # Step 4: Extract NPQ domain scores
        print("\n--- Extracting NPQ Domain Scores ---")
        domain_data, _ = extract_npq_table(pdf_path)
        
        # Step 5: Insert NPQ domain scores
        print("\n--- Inserting NPQ Domain Scores ---")
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
        return True
        
    except Exception as e:
        print(f"Error during test: {e}")
        conn.rollback()
        return False
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
    
    success = test_npq_extraction(pdf_path)
    if success:
        print("NPQ extraction test passed!")
    else:
        print("NPQ extraction test failed!")

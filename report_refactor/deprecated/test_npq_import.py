import os
import sqlite3
from cognitive_importer import create_db, import_pdf_to_db, DB_PATH

def test_npq_import(pdf_path, reset_db=False):
    """
    Test the import of NPQ questions from a PDF file into the database.
    
    Args:
        pdf_path (str): Path to the PDF file
        reset_db (bool): Whether to reset the database before importing
    """
    # Create or reset the database
    create_db(reset=reset_db)
    
    # Import the PDF
    print(f"Importing PDF: {pdf_path}")
    import_pdf_to_db(pdf_path)
    
    # Check the results
    print("\nChecking database for NPQ questions...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get patient ID
    cur.execute("SELECT patient_id FROM patients LIMIT 1")
    patient_id = cur.fetchone()[0]
    
    # Check NPQ questions
    cur.execute("SELECT COUNT(*) FROM npq_questions WHERE patient_id = ?", (patient_id,))
    question_count = cur.fetchone()[0]
    print(f"Found {question_count} NPQ questions for patient {patient_id}")
    
    if question_count > 0:
        # Show sample questions from each domain
        cur.execute("""
            SELECT domain, COUNT(*) 
            FROM npq_questions 
            WHERE patient_id = ? 
            GROUP BY domain
            ORDER BY domain
        """, (patient_id,))
        
        print("\nNPQ Questions by Domain:")
        for domain, count in cur.fetchall():
            print(f"  {domain}: {count} questions")
            
            # Show a sample question from this domain
            cur.execute("""
                SELECT question_number, question_text, score, severity 
                FROM npq_questions 
                WHERE patient_id = ? AND domain = ? 
                ORDER BY question_number
                LIMIT 1
            """, (patient_id, domain))
            
            sample = cur.fetchone()
            if sample:
                q_num, q_text, score, severity = sample
                print(f"    Sample - Q{q_num}: '{q_text[:40]}...' -> {score} - {severity}")
    
    # Check import status
    print("\nImport Status:")
    cur.execute("SELECT section, status FROM test_log WHERE patient_id = ?", (patient_id,))
    for section, status in cur.fetchall():
        print(f"  {section}: {status}")
    
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_npq_import.py <pdf_file> [--reset]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    reset_db = "--reset" in sys.argv
    
    test_npq_import(pdf_path, reset_db)

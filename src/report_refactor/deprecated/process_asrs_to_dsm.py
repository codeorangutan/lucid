#!/usr/bin/env python3
"""
ASRS to DSM-5 Processor

This script processes ASRS responses for all patients and maps them to DSM-5 criteria,
storing the results in the database for future analysis.
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('asrs_to_dsm_processor.log'),
        logging.StreamHandler()
    ]
)

# Import ASRS-DSM mapping
try:
    from asrs_dsm_mapper import DSM5_ASRS_MAPPING, RESPONSE_SCORES, is_met
except ImportError:
    logging.error("Could not import ASRS-DSM mapping. Please ensure asrs_dsm_mapper.py is available.")
    sys.exit(1)

class ASRStoDSMProcessor:
    """Process ASRS responses and map them to DSM-5 criteria."""
    
    def __init__(self, db_path):
        """Initialize with database path."""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def create_tables(self):
        """Create the necessary tables if they don't exist."""
        try:
            self.cursor.executescript("""
                CREATE TABLE IF NOT EXISTS dsm5_criteria (
                    patient_id INTEGER,
                    criterion_id TEXT,
                    criterion_met BOOLEAN,
                    asrs_question INTEGER,
                    asrs_response TEXT,
                    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
                );

                CREATE TABLE IF NOT EXISTS adhd_diagnoses (
                    patient_id INTEGER PRIMARY KEY,
                    inattentive_count INTEGER,
                    hyperactive_count INTEGER,
                    inattentive_met BOOLEAN,
                    hyperactive_met BOOLEAN,
                    adhd_diagnosis BOOLEAN,
                    adhd_type TEXT,
                    diagnosis_date TEXT,
                    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
                );
            """)
            self.conn.commit()
            logging.info("Successfully created DSM-5 tables")
            return True
        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")
            self.conn.rollback()
            return False

    def connect_to_db(self):
        """Connect to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            logging.info(f"Connected to database: {self.db_path}")
            if not self.create_tables():
                return False
            return True
        except sqlite3.Error as e:
            logging.error(f"Error connecting to database: {e}")
            return False
    
    def get_all_patients(self):
        """Get all patient IDs from the database."""
        try:
            self.cursor.execute("SELECT patient_id FROM patients")
            return [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error getting patient IDs: {e}")
            return []
    
    def get_patient_asrs_responses(self, patient_id):
        """Get ASRS responses for a specific patient."""
        try:
            self.cursor.execute(
                "SELECT question_number, response FROM asrs_responses WHERE patient_id = ?",
                (patient_id,)
            )
            return dict(self.cursor.fetchall())
        except sqlite3.Error as e:
            logging.error(f"Error getting ASRS responses for patient {patient_id}: {e}")
            return {}
    
    def clear_existing_data(self, patient_id):
        """Clear existing DSM-5 data for a patient."""
        try:
            self.cursor.execute("DELETE FROM dsm5_criteria WHERE patient_id = ?", (patient_id,))
            self.cursor.execute("DELETE FROM adhd_diagnoses WHERE patient_id = ?", (patient_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error clearing existing data for patient {patient_id}: {e}")
            self.conn.rollback()
    
    def process_patient(self, patient_id):
        """Process ASRS responses and map to DSM-5 criteria for a single patient."""
        logging.info(f"Processing patient {patient_id}")
        
        # Get patient's ASRS responses
        asrs_responses = self.get_patient_asrs_responses(patient_id)
        if not asrs_responses:
            logging.warning(f"No ASRS responses found for patient {patient_id}")
            return False
        
        # Clear existing data
        self.clear_existing_data(patient_id)
        
        # Process each DSM-5 criterion
        inattentive_met = 0
        hyperactive_met = 0
        dsm5_criteria = []
        
        # Process first 9 items (Inattention)
        for i in range(9):
            dsm_crit, _, q_num = DSM5_ASRS_MAPPING[i]
            response = asrs_responses.get(q_num, "N/A")
            criterion_met = is_met(response)
            if criterion_met:
                inattentive_met += 1
            
            criterion_id = f"1{chr(ord('a') + i)}"
            dsm5_criteria.append((
                patient_id, criterion_id, criterion_met,
                q_num, response
            ))
        
        # Process last 9 items (Hyperactivity/Impulsivity)
        for i in range(9, 18):
            dsm_crit, _, q_num = DSM5_ASRS_MAPPING[i]
            response = asrs_responses.get(q_num, "N/A")
            criterion_met = is_met(response)
            if criterion_met:
                hyperactive_met += 1
            
            criterion_id = f"2{chr(ord('a') + i - 9)}"
            dsm5_criteria.append((
                patient_id, criterion_id, criterion_met,
                q_num, response
            ))
        
        try:
            # Insert DSM-5 criteria
            self.cursor.executemany(
                """INSERT INTO dsm5_criteria 
                   (patient_id, criterion_id, criterion_met, asrs_question, asrs_response)
                   VALUES (?, ?, ?, ?, ?)""",
                dsm5_criteria
            )
            
            # Determine ADHD diagnosis and type
            inattentive_criteria_met = inattentive_met >= 5
            hyperactive_criteria_met = hyperactive_met >= 5
            has_adhd = inattentive_criteria_met or hyperactive_criteria_met
            
            if inattentive_criteria_met and hyperactive_criteria_met:
                adhd_type = "Combined"
            elif inattentive_criteria_met:
                adhd_type = "Inattentive"
            elif hyperactive_criteria_met:
                adhd_type = "Hyperactive"
            else:
                adhd_type = None
            
            # Insert ADHD diagnosis
            self.cursor.execute(
                """INSERT INTO adhd_diagnoses 
                   (patient_id, inattentive_count, hyperactive_count,
                    inattentive_met, hyperactive_met, adhd_diagnosis,
                    adhd_type, diagnosis_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (patient_id, inattentive_met, hyperactive_met,
                 inattentive_criteria_met, hyperactive_criteria_met,
                 has_adhd, adhd_type, datetime.now().isoformat())
            )
            
            self.conn.commit()
            logging.info(f"Successfully processed patient {patient_id}")
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Error processing patient {patient_id}: {e}")
            self.conn.rollback()
            return False
    
    def process_all_patients(self):
        """Process all patients in the database."""
        if not self.connect_to_db():
            return False
        
        patient_ids = self.get_all_patients()
        if not patient_ids:
            logging.error("No patients found in database")
            return False
        
        total_patients = len(patient_ids)
        successful = 0
        
        for i, patient_id in enumerate(patient_ids, 1):
            if self.process_patient(patient_id):
                successful += 1
            logging.info(f"Progress: {i}/{total_patients} patients processed")
        
        logging.info(f"Processing complete. Successfully processed {successful}/{total_patients} patients")
        return True
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

def main():
    """Main function to run the processor."""
    script_dir = Path(__file__).parent
    db_path = script_dir / "cognitive_analysis.db"
    
    if not db_path.exists():
        db_path = script_dir.parent / "cognitive_analysis.db"
    
    if not db_path.exists():
        logging.error(f"Database not found at {db_path}")
        sys.exit(1)
    
    processor = ASRStoDSMProcessor(str(db_path))
    try:
        if processor.process_all_patients():
            logging.info("Successfully completed ASRS to DSM-5 processing")
        else:
            logging.error("Failed to process ASRS to DSM-5 mapping")
    finally:
        processor.close()

if __name__ == "__main__":
    main()

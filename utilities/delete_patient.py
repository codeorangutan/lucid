import argparse
import os
import logging
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from db import (
    get_session, CognitiveScore, SubtestResult, ASRSResponse, DSMDiagnosis, DSMCriteriaMet, EpworthResponse, EpworthSummary, NPQDomainScore, NPQResponse
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

JSON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'json'))

def delete_patient_from_db(patient_id):
    """Delete all records for a patient_id from all relevant tables."""
    with get_session() as session:
        models = [CognitiveScore, SubtestResult, ASRSResponse, DSMDiagnosis, DSMCriteriaMet, EpworthResponse, EpworthSummary, NPQDomainScore, NPQResponse]
        total_deleted = 0
        for model in models:
            q = session.query(model).filter(model.patient_id == str(patient_id))
            count = q.count()
            if count > 0:
                logging.info(f"Deleting {count} records from {model.__tablename__} for patient_id={patient_id}")
                q.delete(synchronize_session=False)
                total_deleted += count
        session.commit()
        if total_deleted == 0:
            logging.warning(f"No records found for patient_id={patient_id} in any table.")
        else:
            logging.info(f"Deleted total {total_deleted} records for patient_id={patient_id}.")
    return total_deleted

def delete_json_file(patient_id):
    """Delete the JSON file for the patient if it exists."""
    json_filename = f"{patient_id}.json"
    json_path = os.path.join(JSON_DIR, json_filename)
    if os.path.isfile(json_path):
        try:
            os.remove(json_path)
            logging.info(f"Deleted JSON file: {json_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to delete JSON file: {json_path} -- {e}")
            return False
    else:
        logging.warning(f"JSON file not found: {json_path}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Delete all patient data from DB and optionally remove JSON file.")
    parser.add_argument('patient_id', type=str, help='Patient ID to delete')
    parser.add_argument('--json', action='store_true', help='Also delete the patient JSON file in /src/json')
    args = parser.parse_args()

    deleted = delete_patient_from_db(args.patient_id)
    if args.json:
        delete_json_file(args.patient_id)
    if deleted > 0:
        logging.info(f"Successfully deleted patient {args.patient_id} from database.")
    else:
        logging.info(f"No database records deleted for patient {args.patient_id}.")

if __name__ == "__main__":
    main()

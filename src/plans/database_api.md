# Cognitive Test Database & API Documentation

---

## 1. Database Schema Documentation

### Main Tables

#### `referrals`
Stores patient demographic and referral information.

| Column                | Type      | Description                                 |
|-----------------------|-----------|---------------------------------------------|
| id                    | Integer   | Primary key                                 |
| email                 | String    | Patient email                               |
| mobile                | String    | Patient mobile number                       |
| dob                   | String    | Date of birth                               |
| id_number             | String    | Unique patient identifier                   |
| raw_subject           | String    | Raw subject from referral                   |
| raw_body              | String    | Raw body from referral                      |
| referral_received_time| DateTime  | When referral was received                  |
| test_request_time     | DateTime  | When test was requested                     |
| referrer              | String    | Referrer name                               |
| referrer_email        | String    | Referrer email                              |
| referral_confirmed_time| DateTime | When referral was confirmed                 |
| paid                  | Boolean   | Payment status                              |
| invoice_date          | DateTime  | Date of invoice                             |
| invoice_number        | String    | Invoice number                              |
| test_completed        | Boolean   | If test completed                           |
| retest                | Boolean   | If retest                                   |
| report_unprocessed    | Boolean   | Report not processed                        |
| report_processed      | Boolean   | Report processed                            |
| report_sent_date      | DateTime  | When report sent                            |

#### Other Key Tables (inferred from data_access.py)
- `cognitive_scores`: Cognitive test results summary per patient.
- `subtest_results`: Detailed subtest results per patient.
- `asrs_responses`: ADHD Self-Report Scale responses.
- `dsm_diagnoses`: DASS (Depression, Anxiety, Stress Scale) summary.
- `epworth_summary`: Epworth Sleepiness Scale summary.
- `npq_domain_scores`: NPQ (Neuropsych Questionnaire) domain scores.

##### Common Columns (inferred)
- All test tables use `patient_id` (VARCHAR) to link to `referrals.id_number`.

---

## 2. Data Structure Example

A typical patient’s data (as returned by `fetch_all_patient_data`) is structured as:

```python
{
    "patient": {...},               # Demographics from referrals
    "cognitive_scores": [...],      # List of dicts or tuples with cognitive scores
    "subtests": [...],              # List of subtest result dicts/tuples
    "asrs": [...],                  # List of ASRS responses
    "dass_summary": {...},          # DASS summary
    "dass_items": [...],            # DASS item responses
    "epworth": [...],               # Epworth summary and responses
    "npq_scores": {...},            # NPQ domain scores
    "npq_questions": [...]          # NPQ item responses
}
```

---

## 3. API Specification for Data Access

### Python API Functions

All functions accept a `patient_id` (string) and optional `db_path` (string).

#### Existence and Completeness

- `patient_exists_in_db(patient_id, db_path=None) -> bool`
  - Checks if a patient exists and has any cognitive data.

- `check_data_completeness(patient_id, db_path=None) -> dict`
  - Returns a dict with booleans for each data component (e.g., cognitive_scores, subtests, asrs, dass, epworth, npq).

#### Data Retrieval

- `get_patient_data(patient_id, db_path=None) -> dict`
  - Returns demographic info from `referrals`.

- `get_cognitive_scores(patient_id, db_path=None) -> list`
  - Returns summary cognitive test scores.

- `get_subtest_results(patient_id, db_path=None) -> list`
  - Returns detailed subtest results.

- `get_asrs_responses(patient_id, db_path=None) -> list`
  - Returns ASRS responses.

- `get_dass_data(patient_id, db_path=None) -> dict`
  - Returns DASS summary and item responses.

- `get_epworth_scores(patient_id, db_path=None) -> list`
  - Returns Epworth Sleepiness Scale data.

- `get_npq_data(patient_id, db_path=None) -> dict`
  - Returns NPQ domain scores and item responses.

- `get_domain_scores_for_radar(patient_id, db_path=None) -> (dict, list)`
  - Returns a dict of domain names to percentiles and a list of invalid domains.

- `fetch_all_patient_data(patient_id, db_path=None) -> dict`
  - Returns all the above data in a single dictionary.

### API Usage Example

```python
from report_refactor import data_access

pid = "12345"

if data_access.patient_exists_in_db(pid):
    all_data = data_access.fetch_all_patient_data(pid)
    print(all_data["patient"])
    print(all_data["cognitive_scores"])
    # ...etc.
else:
    print("Patient not found or no data available.")
```

---

## 4. Recommendations for Robust Data Access

- **Error Handling:** All functions catch exceptions and log errors, returning empty or default values if data is missing.
- **Extensibility:** New test tables can be added with corresponding getter functions.
- **Atomic Fetch:** Use `fetch_all_patient_data` for a single-call, all-in-one fetch.
- **Patient ID Consistency:** Always use `referrals.id_number` as the primary patient identifier across tables.
- **Logging:** All operations are logged for traceability.

---

## 5. (Optional) Database Introspection Script

If you want to automatically document or check the schema, here’s a script to list all tables and columns in your SQLite database:

```python
import sqlite3

def print_db_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for (table_name,) in tables:
        print(f"Table: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name});")
        for col in cursor.fetchall():
            print(f"  {col[1]} ({col[2]})")
    conn.close()

# Usage
print_db_schema("lucid_data.db")
```

---

### Summary

- The database is centered on the `referrals` table, with related tables for each cognitive/psychological test.
- Data access is modular and robust, with a clear API for each data type.
- All access is via patient ID, and the API is designed for extensibility and reliability.

If you need more details on a specific table or want to see the output of the introspection script, let me know!

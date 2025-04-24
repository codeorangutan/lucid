import subprocess
import os
import re
import json
import pandas as pd
import tempfile
import sqlite3

# Define the structure of known tests and their subtests
known_subtests_dict = {
    "Verbal Memory Test (VBM)": [
        "Correct Hits - Immediate", "Correct Passes - Immediate",
        "Correct Hits - Delay", "Correct Passes - Delay"
    ],
    "Visual Memory Test (VSM)": [
        "Correct Hits - Immediate", "Correct Passes - Immediate",
        "Correct Hits - Delay", "Correct Passes - Delay"
    ],
    "Finger Tapping Test (FTT)": [
        "Right Taps Average", "Left Taps Average"
    ],
    "Symbol Digit Coding (SDC)": [
        "Correct Responses", "Errors*"
    ],
    "Stroop Test (ST)": [
        "Simple Reaction Time*", "Complex Reaction Time Correct*",
        "Stroop Reaction Time Correct*", "Stroop Commission Errors*"
    ],
    "Shifting Attention Test (SAT)": [
        "Correct Responses", "Errors*", "Correct Reaction Time*"
    ],
    "Continuous Performance Test (CPT)": [
        "Correct Responses", "Omission Errors*", "Commission Errors*",
        "Choice Reaction Time Correct*"
    ],
    "Reasoning Test (RT)": [
        "Correct Responses", "Average Correct Reaction Time*",
        "Commission Errors*", "Omission Errors*"
    ],
    "Four Part Continuous Performance Test": [
        "Average Correct Reaction Time*", "Correct Responses",
        "Incorrect Responses*", "Average Incorrect Reaction Time*",
        "Omission Errors*"
    ]
}

def clean_value(value):
    """Cleans and converts a value to numeric, removing asterisks."""
    if value is None or pd.isna(value):
        return None
    try:
        # Remove asterisks, strip whitespace
        cleaned = str(value).replace('*', '').strip()
        if not cleaned:  # Handle empty strings after cleaning
            return None
        # Convert to numeric, coerce errors to NaN
        numeric_val = pd.to_numeric(cleaned, errors='coerce')
        if pd.isna(numeric_val):
            return None
        
        # Validate the value - reject extreme outliers
        if numeric_val < -100 or numeric_val > 1000:
            print(f"Warning: Extreme value detected: {numeric_val}. Ignoring.")
            return None
            
        return float(numeric_val)
    except Exception as e:
        print(f"Error cleaning value '{value}': {str(e)}")
        return None

def extract_tables_from_pdf(pdf_path, page, method):
    """Extract tables from PDF using tabula-java directly."""
    # Create a temporary file for the JSON output
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_file.close()
    
    try:
        # Base command
        cmd = [
            'java', '-jar', 'tabula-java.jar',
            '-p', str(page),  # page number
            '-f', 'JSON',     # format
            '-o', temp_file.name,  # output file
        ]
        
        # Add method-specific options
        if method == "stream":
            cmd.append("-l")
        elif method == "lattice":
            cmd.append("-t")
        elif method == "stream_guess":
            cmd.extend(["-l", "-g"])
        elif method == "lattice_guess":
            cmd.extend(["-t", "-g"])
        
        # Add the PDF path
        cmd.append(pdf_path)
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error running tabula-java: {result.stderr}")
            return []
            
        # Read the JSON output
        if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
            with open(temp_file.name, 'r') as f:
                try:
                    tables_data = json.load(f)
                    return tables_data
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                    return []
        else:
            print(f"Output file is empty or doesn't exist")
            return []
    
    except Exception as e:
        print(f"Error extracting tables: {str(e)}")
        return []
    
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)

def identify_subtest_table(df):
    """Identify if a table contains cognitive subtest data."""
    if df.empty or df.shape[1] < 3:
        return False
    
    # Keywords that indicate this might be a subtest table
    subtest_keywords = [
        "Correct Responses", "Reaction Time", "Errors", 
        "Taps Average", "Hits", "Passes", "Commission",
        "Omission", "Standard", "Percentile"
    ]
    
    # Check if any keywords are present in the table
    for keyword in subtest_keywords:
        for col in df.columns:
            if df[col].astype(str).str.contains(keyword).any():
                return True
    
    return False

def identify_test_type(df):
    """Identify which cognitive test this table represents."""
    if df.empty:
        return None
    
    # Check for test names in the table
    for test_name in known_subtests_dict.keys():
        # Check if the test name appears in any cell
        for col in df.columns:
            if df[col].astype(str).str.contains(test_name, regex=False).any():
                return test_name
    
    # If we couldn't find a direct match, look for subtest names
    subtest_matches = {}
    for test_name, subtests in known_subtests_dict.items():
        count = 0
        for subtest in subtests:
            for col in df.columns:
                if df[col].astype(str).str.contains(subtest, regex=False).any():
                    count += 1
                    break
        if count > 0:
            subtest_matches[test_name] = count
    
    if subtest_matches:
        # Return the test with the most matching subtests
        return max(subtest_matches, key=subtest_matches.get)
    
    return None

def extract_subtest_scores(df, test_name):
    """Extract subtest scores from a DataFrame."""
    if df.empty or test_name is None:
        return []
    
    results = []
    expected_subtests = known_subtests_dict.get(test_name, [])
    
    # Try to identify which columns contain what data
    # Usually: 0=Subtest, 1=Score, 2=Standard, 3=Percentile
    col_subtest = None
    col_score = None
    col_standard = None
    col_percentile = None
    
    # Try to identify column roles by looking at headers
    for i, col in enumerate(df.columns):
        # Check first few rows for column identifiers
        for row_idx in range(min(3, len(df))):
            if row_idx < len(df):
                cell_value = str(df.iloc[row_idx, i]).lower()
                if any(keyword in cell_value for keyword in ["test", "subtest", "metric"]):
                    col_subtest = i
                elif any(keyword in cell_value for keyword in ["raw", "score"]):
                    col_score = i
                elif any(keyword in cell_value for keyword in ["standard", "std"]):
                    col_standard = i
                elif any(keyword in cell_value for keyword in ["percentile", "%ile"]):
                    col_percentile = i
    
    # If we couldn't identify columns by headers, use default positions
    if col_subtest is None:
        col_subtest = 0
    if col_score is None and df.shape[1] > 1:
        col_score = 1
    if col_standard is None and df.shape[1] > 2:
        col_standard = 2
    if col_percentile is None and df.shape[1] > 3:
        col_percentile = 3
    
    # Special case for Four Part CPT
    current_part = None
    is_fpcpt = (test_name == "Four Part Continuous Performance Test")
    
    # Skip the header row(s)
    start_row = 0
    for i in range(min(3, len(df))):
        if any(keyword in str(df.iloc[i]).lower() for keyword in ["raw", "score", "standard", "percentile"]):
            start_row = i + 1
            break
    
    # Process each row
    for row_idx in range(start_row, len(df)):
        row = df.iloc[row_idx]
        
        # Skip rows with missing subtest name
        if col_subtest >= len(row) or pd.isna(row.iloc[col_subtest]):
            continue
            
        subtest_name = str(row.iloc[col_subtest]).strip()
        if not subtest_name:
            continue
        
        # Check for FPCPT part headers
        if is_fpcpt and re.match(r"Part\s+\d+", subtest_name):
            current_part = subtest_name
            continue
        
        # Check if this matches a known subtest
        matched_subtest = None
        for expected_sub in expected_subtests:
            if expected_sub in subtest_name:
                matched_subtest = expected_sub
                break
        
        if matched_subtest:
            # Extract values
            score = None
            standard = None
            percentile = None
            
            if col_score is not None and col_score < len(row):
                score = clean_value(row.iloc[col_score])
            if col_standard is not None and col_standard < len(row):
                standard = clean_value(row.iloc[col_standard])
            if col_percentile is not None and col_percentile < len(row):
                percentile = clean_value(row.iloc[col_percentile])
            
            # For FPCPT, add part number
            if is_fpcpt and current_part:
                full_subtest_name = f"{matched_subtest} - {current_part}"
            else:
                full_subtest_name = matched_subtest
            
            # Only add if we have at least one valid value
            if score is not None or standard is not None or percentile is not None:
                results.append({
                    'test_name': test_name,
                    'metric': full_subtest_name,
                    'score': score,
                    'standard': standard,
                    'percentile': percentile
                })
    
    return results

def extract_subtests_from_pdf(pdf_path, patient_id=None):
    """Extract cognitive subtests from PDF."""
    all_results = {}  # Use a dictionary to avoid duplicates
    
    print(f"Starting extraction from {pdf_path}...")
    
    # Check Java installation
    try:
        java_version = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT).decode()
        print(f"Java detected: {java_version.splitlines()[0]}")
    except Exception as e:
        print(f"Error: Java not found. {str(e)}")
        return []
    
    # Extraction methods to try
    methods = ["stream_guess", "lattice_guess", "stream", "lattice"]
    
    # Process each page
    for page_num in [1, 2, 3]:
        print(f"\nProcessing Page {page_num}...")
        
        # Try each extraction method
        for method in methods:
            print(f"  Trying method: {method}")
            
            # Extract tables
            tables_data = extract_tables_from_pdf(pdf_path, page_num, method)
            if not tables_data:
                continue
            
            print(f"  Found {len(tables_data)} tables with {method}")
            
            # Process each table
            for table_data in tables_data:
                # Convert to DataFrame
                data = []
                for row in table_data.get('data', []):
                    row_data = []
                    for cell in row:
                        row_data.append(cell.get('text', ''))
                    if any(row_data):  # Skip empty rows
                        data.append(row_data)
                
                if not data:
                    continue
                    
                df = pd.DataFrame(data)
                
                # Check if this is a subtest table
                if not identify_subtest_table(df):
                    continue
                
                # Identify test type
                test_name = identify_test_type(df)
                if not test_name:
                    continue
                
                print(f"  Found table for: {test_name}")
                
                # Extract scores
                scores = extract_subtest_scores(df, test_name)
                
                # Add to results dictionary using composite key to avoid duplicates
                for score in scores:
                    key = (score['test_name'], score['metric'])
                    
                    # Only replace existing entry if new one has more values
                    if key in all_results:
                        existing = all_results[key]
                        # Count non-None values in existing and new
                        existing_count = sum(1 for v in [existing['score'], existing['standard'], existing['percentile']] if v is not None)
                        new_count = sum(1 for v in [score['score'], score['standard'], score['percentile']] if v is not None)
                        
                        # Replace if new has more values, or if equal but score is present in new
                        if new_count > existing_count or (new_count == existing_count and score['score'] is not None and existing['score'] is None):
                            all_results[key] = score
                    else:
                        all_results[key] = score
    
    # Convert to format for database insertion
    subtests_data = []
    for result in all_results.values():
        subtests_data.append((
            patient_id,
            result['test_name'],
            result['metric'],
            result['score'],
            result['standard'],
            result['percentile']
        ))
    
    return subtests_data

def save_to_database(subtests, db_path="cognitive_analysis.db"):
    """Save extracted subtests to the database."""
    if not subtests:
        print("No subtests to save.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subtest_results'")
        if not cursor.fetchone():
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT,
                    subtest_name TEXT,
                    metric TEXT,
                    score REAL,
                    standard_score INTEGER,
                    percentile INTEGER,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                )
            ''')
        else:
            # Clear existing data for this patient
            cursor.execute("DELETE FROM subtest_results WHERE patient_id = ?", (subtests[0][0],))
            print(f"Cleared existing data for patient {subtests[0][0]}")
        
        # Insert data
        cursor.executemany('''
            INSERT INTO subtest_results 
            (patient_id, subtest_name, metric, score, standard_score, percentile)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', subtests)
        
        conn.commit()
        print(f"Successfully saved {len(subtests)} subtests to database.")
    
    except Exception as e:
        print(f"Error saving to database: {str(e)}")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Test with specific PDF
    pdf_path = "40277.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} not found!")
    else:
        patient_id = "40277"  # Extract from filename
        
        # Extract subtests
        subtests = extract_subtests_from_pdf(pdf_path, patient_id)
        
        print("\n=== EXTRACTION RESULTS ===")
        print(f"Total subtests extracted: {len(subtests)}")
        for subtest in subtests:
            print(f"Test: {subtest[1]}, Metric: {subtest[2]}, Score: {subtest[3]}, Standard: {subtest[4]}, Percentile: {subtest[5]}")
        
        # Save to database
        save_to_database(subtests)

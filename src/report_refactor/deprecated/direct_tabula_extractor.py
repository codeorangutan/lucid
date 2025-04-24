import subprocess
import json
import pandas as pd
import os
import re
import tempfile

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

# Map main tests expected on each page (helps disambiguate)
tests_on_page = {
    1: ["Verbal Memory Test (VBM)", "Visual Memory Test (VSM)", "Finger Tapping Test (FTT)"],
    2: ["Symbol Digit Coding (SDC)", "Stroop Test (ST)", "Shifting Attention Test (SAT)",
        "Continuous Performance Test (CPT)", "Reasoning Test (RT)"],
    3: ["Four Part Continuous Performance Test"]
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
        return float(numeric_val)
    except Exception as e:
        print(f"Error cleaning value '{value}': {str(e)}")
        return None

def identify_test_from_table(df, expected_tests):
    """Identify which test this table belongs to based on content."""
    if df.empty or df.shape[1] < 2:
        return None
    
    # Extract first column values (potential subtest names)
    first_col_values = []
    for val in df.iloc[:, 0]:
        if val is not None and not pd.isna(val):
            first_col_values.append(str(val).strip())
    
    print(f"DEBUG: First column values: {first_col_values}")
    
    # Check for matches with known subtests
    matches = {}
    for test_name in expected_tests:
        expected_subtests = known_subtests_dict.get(test_name, [])
        count = 0
        
        for value in first_col_values:
            # Check for exact match
            if value in expected_subtests:
                count += 1
                continue
                
            # Check for partial match
            for subtest in expected_subtests:
                if subtest in value:
                    count += 1
                    break
        
        if count > 0:
            matches[test_name] = count
            print(f"DEBUG: Found {count} matches for {test_name}")
    
    if not matches:
        # Special check for FPCPT
        if "Four Part Continuous Performance Test" in expected_tests:
            for value in first_col_values:
                if re.match(r"Part\s+\d+", value):
                    return "Four Part Continuous Performance Test"
        return None
    
    # Return the test with the most matches
    return max(matches, key=matches.get)

def extract_tables_with_tabula_java(pdf_path, page):
    """Extract tables from PDF using tabula-java directly."""
    # Create a temporary file for the JSON output
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_file.close()
    
    try:
        # Run tabula-java with subprocess
        cmd = [
            'java', '-jar', 'tabula-java.jar',
            '--pages', str(page),
            '--format', 'JSON',
            '--outfile', temp_file.name,
            pdf_path
        ]
        print(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
        # Read the JSON output
        with open(temp_file.name, 'r') as f:
            tables_data = json.load(f)
        
        # Convert JSON tables to pandas DataFrames
        dataframes = []
        for table_data in tables_data:
            # Extract data from JSON
            data = []
            for row in table_data.get('data', []):
                row_data = []
                for cell in row:
                    row_data.append(cell.get('text', ''))
                if any(row_data):  # Skip empty rows
                    data.append(row_data)
            
            if data:
                df = pd.DataFrame(data)
                dataframes.append(df)
        
        return dataframes
    
    except Exception as e:
        print(f"Error extracting tables: {str(e)}")
        return []
    
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)

def extract_subtests_from_pdf(pdf_path, patient_id=None):
    """Extract cognitive subtests from PDF."""
    all_results = {}
    subtests_data = []
    
    print(f"Starting extraction from {pdf_path}...")
    
    # Check Java installation
    try:
        java_version = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT).decode()
        print(f"Java detected: {java_version.splitlines()[0]}")
    except Exception as e:
        print(f"Error: Java not found. {str(e)}")
        return []
    
    # Process each page
    for page_num in [1, 2, 3]:
        print(f"\nProcessing Page {page_num}...")
        
        # Extract tables using tabula-java
        tables = extract_tables_with_tabula_java(pdf_path, page_num)
        
        if not tables:
            print(f"  No tables found on page {page_num}.")
            continue
        
        print(f"  Found {len(tables)} table(s) on page {page_num}.")
        expected_tests = tests_on_page.get(page_num, [])
        
        # Process each table
        for i, df in enumerate(tables):
            print(f"\n  Table {i+1} shape: {df.shape}")
            print(df.head())
            
            if df.empty or df.shape[1] < 3:
                print(f"  Skipping empty or narrow table {i+1}.")
                continue
            
            # Identify which test this table belongs to
            test_name = identify_test_from_table(df, expected_tests)
            if not test_name:
                print(f"  Could not identify test for table {i+1}.")
                continue
            
            print(f"  Table {i+1} identified as: {test_name}")
            expected_subtests = known_subtests_dict.get(test_name, [])
            
            # Determine column indices (default: 0=Subtest, 1=Score, 2=Standard, 3=Percentile)
            col_subtest = 0
            col_score = 1 if df.shape[1] > 1 else None
            col_standard = 2 if df.shape[1] > 2 else None
            col_percentile = 3 if df.shape[1] > 3 else None
            
            # Handle Four Part CPT special case
            current_part = None
            is_fpcpt = (test_name == "Four Part Continuous Performance Test")
            
            # Process each row
            for row_idx, row in df.iterrows():
                # Skip header row
                if row_idx == 0 and any('score' in str(val).lower() for val in row if val is not None and not pd.isna(val)):
                    continue
                
                # Get subtest name
                if col_subtest >= len(row) or pd.isna(row.iloc[col_subtest]):
                    continue
                    
                subtest_name = str(row.iloc[col_subtest]).strip()
                if not subtest_name:
                    continue
                
                # Check for FPCPT part headers
                if is_fpcpt and re.match(r"Part\s+\d+", subtest_name):
                    current_part = subtest_name
                    print(f"    Entering {current_part}")
                    continue
                
                # Check if this is a known subtest
                matched_subtest = None
                for expected_sub in expected_subtests:
                    if expected_sub in subtest_name:
                        matched_subtest = expected_sub
                        break
                
                if matched_subtest:
                    try:
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
                        
                        # Store result
                        result_key = (test_name, full_subtest_name)
                        all_results[result_key] = {
                            'Score': score,
                            'Standard': standard,
                            'Percentile': percentile
                        }
                        
                        print(f"    Extracted: {result_key} -> Score: {score}, Standard: {standard}, Percentile: {percentile}")
                    except Exception as e:
                        print(f"    Error extracting values for {subtest_name}: {str(e)}")
    
    # Convert results to database format
    for (test_name, metric), values in all_results.items():
        subtests_data.append((
            patient_id,
            test_name,
            metric,
            values['Score'],
            values['Standard'],
            values['Percentile']
        ))
    
    return subtests_data

if __name__ == "__main__":
    # Test with specific PDF
    pdf_path = "40277.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} not found!")
    else:
        patient_id = "40277"
        results = extract_subtests_from_pdf(pdf_path, patient_id)
        
        print("\n=== EXTRACTION RESULTS ===")
        print(f"Total subtests extracted: {len(results)}")
        for result in results:
            print(f"Test: {result[1]}, Metric: {result[2]}, Score: {result[3]}, Standard: {result[4]}, Percentile: {result[5]}")

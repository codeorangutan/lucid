import camelot
import pandas as pd
import numpy as np
import re
import os
import traceback
import warnings
import time
import sys
warnings.filterwarnings('ignore')  # Suppress warnings

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
        "Correct Responses", "Errors"
    ],
    "Stroop Test (ST)": [
        "Simple Reaction Time", "Complex Reaction Time Correct",
        "Stroop Reaction Time Correct", "Stroop Commission Errors"
    ],
    "Shifting Attention Test (SAT)": [
        "Correct Responses", "Errors", "Correct Reaction Time"
    ],
    "Continuous Performance Test (CPT)": [
        "Correct Responses", "Omission Errors", "Commission Errors",
        "Choice Reaction Time Correct"
    ],
    "Reasoning Test (RT)": [
        "Correct Responses", "Average Correct Reaction Time",
        "Commission Errors", "Omission Errors"
    ],
    "Four Part Continuous Performance Test": [
        "Average Correct Reaction Time", "Correct Responses",
        "Incorrect Responses", "Average Incorrect Reaction Time",
        "Omission Errors"
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
    """Clean and convert a value to numeric, removing asterisks."""
    if value is None or pd.isna(value) or value == '':
        return None
    try:
        # Remove asterisks, strip whitespace
        cleaned = str(value).replace('*', '').replace('\n', ' ').strip()
        if not cleaned:  # Handle empty strings after cleaning
            return None
        # Convert to numeric, coerce errors to NaN
        numeric_val = pd.to_numeric(cleaned, errors='coerce')
        if pd.isna(numeric_val):
            return None
        return float(numeric_val)
    except Exception:
        return None

def identify_test_in_table(df, expected_tests):
    """Identify which test this table contains data for."""
    # First check for direct test name mentions with exact matching
    for test_name in expected_tests:
        for i, row in df.iterrows():
            for j, val in enumerate(row):
                if pd.isna(val):
                    continue
                val_str = str(val).strip()
                
                # Exact match for test name
                if test_name == val_str:
                    return test_name
                
                # Look for exact abbreviation matches in parentheses to distinguish similar tests
                # For example: "Verbal Memory Test (VBM)" vs "Visual Memory Test (VSM)"
                if test_name in val_str:
                    # Extract abbreviation from test name
                    test_abbr_match = re.search(r'\((.*?)\)', test_name)
                    if test_abbr_match:
                        test_abbr = test_abbr_match.group(1)
                        # Check if this exact abbreviation is in the value
                        if f"({test_abbr})" in val_str:
                            return test_name
    
    # If no direct test name found, check for subtests with weighted scoring
    subtest_scores = {test: 0 for test in expected_tests}
    for test_name in expected_tests:
        subtests = known_subtests_dict.get(test_name, [])
        for subtest in subtests:
            for i, row in df.iterrows():
                for j, val in enumerate(row):
                    if pd.isna(val):
                        continue
                    val_str = str(val).strip()
                    
                    # Exact match gets higher score
                    if subtest == val_str:
                        subtest_scores[test_name] += 2
                        break
                    # Partial match gets lower score
                    elif subtest in val_str:
                        subtest_scores[test_name] += 1
                        break
    
    # Return the test with the highest subtest score
    if subtest_scores:
        max_score = max(subtest_scores.values())
        if max_score > 0:
            # If multiple tests have the same score, prioritize by position in expected_tests
            max_tests = [test for test, score in subtest_scores.items() if score == max_score]
            if max_tests:
                return max_tests[0]
    
    return None

def process_table(table, expected_tests):
    """Process a single table to extract cognitive test data."""
    extracted_data = []
    df = table.df
    
    if df.empty or df.shape[1] < 2:  # Need at least 2 columns for test name and score
        return []
    
    # Try to identify the test from the table
    current_test = identify_test_in_table(df, expected_tests)
    
    if not current_test:
        return []
    
    # Now extract the subtests
    expected_subtests = known_subtests_dict.get(current_test, [])
    
    # First pass: find rows containing subtests
    subtest_rows = {}
    for i, row in df.iterrows():
        for j, val in enumerate(row):
            if pd.isna(val):
                continue
            
            val_str = str(val).strip()
            for subtest in expected_subtests:
                # Check for exact match or if the subtest is contained in the value
                if subtest == val_str or subtest in val_str:
                    subtest_rows[subtest] = (i, j)
                    break
    
    # Second pass: extract values for each subtest
    for subtest, (row_idx, col_idx) in subtest_rows.items():
        row = df.iloc[row_idx]
        
        # Look for numeric values in the next few columns
        score, standard, percentile = None, None, None
        numeric_values = []
        
        # Check for values in the same row
        for k in range(col_idx+1, min(col_idx+5, len(row))):
            if k < len(row):
                val_k = row.iloc[k]
                num_val = clean_value(val_k)
                if num_val is not None:
                    numeric_values.append(num_val)
        
        # If we didn't find values in the same row, try looking in the next row at the same position
        if not numeric_values and row_idx + 1 < len(df):
            next_row = df.iloc[row_idx + 1]
            for k in range(col_idx, min(col_idx+5, len(next_row))):
                if k < len(next_row):
                    val_k = next_row.iloc[k]
                    num_val = clean_value(val_k)
                    if num_val is not None:
                        numeric_values.append(num_val)
        
        # Special handling for Finger Tapping Test
        if current_test == "Finger Tapping Test (FTT)" and not numeric_values:
            # Look for values in a wider range of columns
            for k in range(0, len(row)):
                if k != col_idx:  # Skip the column with the subtest name
                    val_k = row.iloc[k]
                    num_val = clean_value(val_k)
                    if num_val is not None:
                        numeric_values.append(num_val)
        
        # Assign values based on position
        if len(numeric_values) >= 1:
            score = numeric_values[0]
        if len(numeric_values) >= 2:
            standard = numeric_values[1]
        if len(numeric_values) >= 3:
            percentile = numeric_values[2]
        
        # Special handling for Four Part CPT - sometimes the values are split across multiple rows
        if current_test == "Four Part Continuous Performance Test" and (score is None or standard is None):
            # Look in the next few rows for additional values
            for offset in range(1, 3):
                if row_idx + offset < len(df):
                    next_row = df.iloc[row_idx + offset]
                    for k in range(len(next_row)):
                        val_k = next_row.iloc[k]
                        num_val = clean_value(val_k)
                        if num_val is not None:
                            if score is None:
                                score = num_val
                            elif standard is None:
                                standard = num_val
                            elif percentile is None:
                                percentile = num_val
                                break
        
        if score is not None or standard is not None or percentile is not None:
            extracted_data.append((current_test, subtest, score, standard, percentile))
    
    return extracted_data

def extract_subtests_from_pdf(pdf_path, patient_id=None, debug=False):
    """Extract cognitive subtests from a PDF report using camelot - optimized version."""
    if debug:
        print(f"Starting extraction from {pdf_path}...")
    
    all_extracted_data = []
    
    # Track which tests we've already found to avoid unnecessary processing
    found_tests = set()
    # Track which test-subtest combinations we've already found to avoid duplicates
    found_test_subtests = set()
    
    # Process each page directly without saving intermediate CSVs
    for page_num in [1, 2, 3]:
        if debug:
            print(f"\nProcessing page {page_num}...")
        
        expected_tests = [test for test in tests_on_page.get(page_num, []) if test not in found_tests]
        
        # Skip this page if we've already found all expected tests
        if not expected_tests:
            if debug:
                print(f"  Skipping page {page_num} - all tests already found")
            continue
        
        # Try lattice mode first (usually more accurate for structured tables)
        try:
            if debug:
                print(f"  Trying lattice mode...")
            
            tables = camelot.read_pdf(
                pdf_path,
                pages=str(page_num),
                flavor='lattice'
            )
            
            if debug:
                print(f"  Found {len(tables)} tables with lattice mode")
            
            # Process each table directly
            for i, table in enumerate(tables):
                if debug:
                    print(f"  Processing table {i+1} (Shape: {table.df.shape}, Accuracy: {table.accuracy:.2f}%)")
                
                # Skip tables with very low accuracy
                if table.accuracy < 50:
                    if debug:
                        print(f"  Skipping table {i+1} due to low accuracy: {table.accuracy:.2f}%")
                    continue
                
                # Extract data from this table
                extracted_data = process_table(table, expected_tests)
                
                if extracted_data:
                    # Only add non-duplicate test-subtest combinations
                    new_data = []
                    for test, subtest, score, standard, percentile in extracted_data:
                        key = (test, subtest)
                        if key not in found_test_subtests:
                            found_test_subtests.add(key)
                            new_data.append((test, subtest, score, standard, percentile))
                    
                    if new_data:
                        all_extracted_data.extend(new_data)
                        if debug:
                            print(f"  Extracted {len(new_data)} new items from table {i+1}")
                        
                        # Update found tests
                        for test, _, _, _, _ in new_data:
                            found_tests.add(test)
            
        except Exception as e:
            if debug:
                print(f"  Error with lattice mode on page {page_num}: {str(e)}")
        
        # Update expected tests based on what we've found
        expected_tests = [test for test in expected_tests if test not in found_tests]
        
        # Only try stream mode if we still have tests to find
        if expected_tests:
            try:
                if debug:
                    print(f"  Trying stream mode...")
                
                tables = camelot.read_pdf(
                    pdf_path,
                    pages=str(page_num),
                    flavor='stream'
                )
                
                if debug:
                    print(f"  Found {len(tables)} tables with stream mode")
                
                # Process each table directly
                for i, table in enumerate(tables):
                    if debug:
                        print(f"  Processing table {i+1} (Shape: {table.df.shape}, Accuracy: {table.accuracy:.2f}%)")
                    
                    # Skip tables with very low accuracy
                    if table.accuracy < 50:
                        if debug:
                            print(f"  Skipping table {i+1} due to low accuracy: {table.accuracy:.2f}%")
                        continue
                    
                    # Extract data from this table
                    extracted_data = process_table(table, expected_tests)
                    
                    if extracted_data:
                        # Only add non-duplicate test-subtest combinations
                        new_data = []
                        for test, subtest, score, standard, percentile in extracted_data:
                            key = (test, subtest)
                            if key not in found_test_subtests:
                                found_test_subtests.add(key)
                                new_data.append((test, subtest, score, standard, percentile))
                        
                        if new_data:
                            all_extracted_data.extend(new_data)
                            if debug:
                                print(f"  Extracted {len(new_data)} new items from table {i+1}")
                            
                            # Update found tests
                            for test, _, _, _, _ in new_data:
                                found_tests.add(test)
                
            except Exception as e:
                if debug:
                    print(f"  Error with stream mode on page {page_num}: {str(e)}")
        
        # Update expected tests again
        expected_tests = [test for test in expected_tests if test not in found_tests]
        
        # If we've found all tests for this page, we can skip to the next page
        if not expected_tests:
            if debug:
                print(f"  Found all expected tests for page {page_num}")
    
    # Deduplicate the data with improved logic
    unique_data = {}
    for test, subtest, score, standard, percentile in all_extracted_data:
        key = (test, subtest)
        
        # If we already have this test/subtest, use a scoring system to determine which to keep
        if key in unique_data:
            existing = unique_data[key]
            
            # Count non-None values
            existing_non_none = sum(1 for v in existing[2:5] if v is not None)
            current_non_none = sum(1 for v in (score, standard, percentile) if v is not None)
            
            # Prefer entries with more non-None values
            if current_non_none > existing_non_none:
                unique_data[key] = (test, subtest, score, standard, percentile)
            elif current_non_none == existing_non_none:
                # If tied, prefer entries with score values in reasonable ranges
                existing_score, existing_std, existing_pct = existing[2:5]
                
                # Check if current values are more reasonable
                current_better = False
                
                # Standard scores typically range from 40-160
                if standard is not None and existing_std is not None:
                    if 40 <= standard <= 160 and (existing_std < 40 or existing_std > 160):
                        current_better = True
                
                # Percentiles range from 0-100
                if percentile is not None and existing_pct is not None:
                    if 0 <= percentile <= 100 and (existing_pct < 0 or existing_pct > 100):
                        current_better = True
                
                if current_better:
                    unique_data[key] = (test, subtest, score, standard, percentile)
        else:
            unique_data[key] = (test, subtest, score, standard, percentile)
    
    # Convert to database format
    subtests_data = []
    for test_name, metric, score, standard, percentile in unique_data.values():
        subtests_data.append((
            patient_id,
            test_name,
            metric,
            score,
            standard,
            percentile
        ))
    
    return subtests_data

def extract_and_save(pdf_path, patient_id=None, output_file=None, debug=False):
    """Extract data and save to CSV in one function."""
    if patient_id is None:
        # Try to extract patient ID from filename
        base_name = os.path.basename(pdf_path)
        patient_match = re.match(r'^(\d+)', base_name)
        if patient_match:
            patient_id = patient_match.group(1)
        else:
            patient_id = "unknown"
    
    if output_file is None:
        output_file = f"extracted_cognitive_data_{patient_id}.csv"
    
    # Extract the data
    start_time = time.time()
    results = extract_subtests_from_pdf(pdf_path, patient_id, debug=debug)
    end_time = time.time()
    
    if debug:
        print(f"\n=== EXTRACTION RESULTS ===")
        print(f"Total subtests extracted: {len(results)}")
        print(f"Extraction time: {end_time - start_time:.2f} seconds")
        
        # Group by test for better readability
        tests = {}
        for result in results:
            test = result[1]
            if test not in tests:
                tests[test] = []
            tests[test].append(result)
        
        for test, items in tests.items():
            print(f"\n{test}:")
            for item in items:
                print(f"  {item[2]}: Score={item[3]}, Standard={item[4]}, Percentile={item[5]}")
    
    # Save to CSV
    output_df = pd.DataFrame(
        results, 
        columns=["PatientID", "Test", "Subtest", "Score", "Standard", "Percentile"]
    )
    output_df.to_csv(output_file, index=False)
    
    if debug:
        print(f"\nExtracted data saved to {output_file}")
    
    return results

def get_cognitive_subtests(pdf_path, patient_id=None, debug=False):
    """
    Function to integrate with cognitive_importer.py - returns data in format ready for database import.
    
    Args:
        pdf_path (str): Path to the PDF file
        patient_id (str, optional): Patient ID. If None, will try to extract from filename.
        debug (bool, optional): Whether to print debug information.
        
    Returns:
        list: List of tuples containing (patient_id, test_name, subtest, raw_score, standard_score, percentile)
    """
    try:
        # Extract data from PDF
        results = extract_subtests_from_pdf(pdf_path, patient_id, debug=debug)
        
        if not results:
            if debug:
                print(f"No cognitive subtest data found in {pdf_path}")
            return []
        
        # Format data for database import
        formatted_results = []
        for pid, test, subtest, raw, std, pct in results:
            # Ensure all values are in the correct format
            formatted_results.append((
                str(pid) if pid is not None else None,
                str(test) if test is not None else None,
                str(subtest) if subtest is not None else None,
                float(raw) if raw is not None else None,
                float(std) if std is not None else None,
                float(pct) if pct is not None else None
            ))
        
        return formatted_results
    
    except Exception as e:
        if debug:
            print(f"Error extracting cognitive subtests: {str(e)}")
            traceback.print_exc()
        return []

if __name__ == "__main__":
    # Default to 40277.pdf if no argument provided
    pdf_file = "40277.pdf"
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    
    if not os.path.exists(pdf_file):
        print(f"Error: File {pdf_file} not found!")
        sys.exit(1)
    
    # Extract patient ID from filename
    base_name = os.path.basename(pdf_file)
    patient_match = re.match(r'^(\d+)', base_name)
    patient_id = patient_match.group(1) if patient_match else "unknown"
    
    print(f"Processing {pdf_file} for patient {patient_id}...")
    
    # Extract and save data
    extract_and_save(pdf_file, patient_id, debug=True)

import camelot
import pandas as pd
import numpy as np
import re
import os
import tempfile
import PyPDF2
import traceback
import warnings
import time
import sys
import argparse
warnings.filterwarnings('ignore')  # Suppress warnings

# Define the structure of known tests and their subtests
# *** REMOVED trailing asterisks from subtest names here for cleaner matching ***
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
        "Correct Responses", "Errors" # Removed *
    ],
    "Stroop Test (ST)": [
        "Simple Reaction Time", # Removed *
        "Complex Reaction Time Correct", # Removed *
        "Stroop Reaction Time Correct", # Removed *
        "Stroop Commission Errors" # Removed *
    ],
    "Shifting Attention Test (SAT)": [
        "Correct Responses", "Errors", # Removed *
        "Correct Reaction Time" # Removed *
    ],
    "Continuous Performance Test (CPT)": [
        "Correct Responses", "Omission Errors", # Removed *
        "Commission Errors", # Removed *
        "Choice Reaction Time Correct" # Removed *
    ],
    "Reasoning Test (RT)": [
        "Correct Responses", "Average Correct Reaction Time", # Removed *
        "Commission Errors", # Removed *
        "Omission Errors" # Removed *
    ],
    "Four Part Continuous Performance Test": [
        "Average Correct Reaction Time", # Removed *
        "Correct Responses",
        "Incorrect Responses", # Removed *
        "Average Incorrect Reaction Time", # Removed * (Assuming this exists based on pattern)
        "Omission Errors" # Removed *
    ]
}

# --- Create a reverse lookup: subtest -> test_name ---
subtest_to_test_map = {}
for test, subtests in known_subtests_dict.items():
    for sub in subtests:
        subtest_to_test_map[sub.strip()] = test.strip()


# Map main tests expected on each page (helps disambiguate)
tests_on_page = {
    1: ["Verbal Memory Test (VBM)", "Visual Memory Test (VSM)", "Finger Tapping Test (FTT)"],
    2: ["Symbol Digit Coding (SDC)", "Stroop Test (ST)", "Shifting Attention Test (SAT)",
        "Continuous Performance Test (CPT)", "Reasoning Test (RT)"],
    3: ["Four Part Continuous Performance Test"]
}

def identify_test_in_table(df, expected_tests):
    """Identify which test this table contains data for."""
    test_scores = {test: 0 for test in expected_tests}
    
    # First check if the test name is explicitly mentioned in the table
    for i, row in df.iterrows():
        for j, val in enumerate(row):
            if pd.isna(val):
                continue
            
            val_str = str(val).strip()
            
            # Check for exact test name match first
            for test in expected_tests:
                if test.lower() == val_str.lower():
                    test_scores[test] += 10  # Give high score for exact match
                elif test.lower() in val_str.lower():
                    test_scores[test] += 5   # Give medium score for partial match
    
    # Then check for subtests to confirm the test type
    for test, subtests in known_subtests_dict.items():
        if test not in expected_tests:
            continue
        
        for subtest in subtests:
            for i, row in df.iterrows():
                for j, val in enumerate(row):
                    if pd.isna(val):
                        continue
                    
                    val_str = str(val).strip()
                    
                    # Check for exact subtest match first
                    if subtest.lower() == val_str.lower():
                        test_scores[test] += 2  # Give good score for exact subtest match
                    elif subtest.lower() in val_str.lower():
                        test_scores[test] += 1  # Give small score for partial subtest match
    
    # Special case for distinguishing between similar tests
    # For example, Verbal Memory Test vs Visual Memory Test
    if "Verbal Memory Test (VBM)" in test_scores and "Visual Memory Test (VSM)" in test_scores:
        # Check for specific keywords to disambiguate
        for i, row in df.iterrows():
            for j, val in enumerate(row):
                if pd.isna(val):
                    continue
                
                val_str = str(val).strip().lower()
                
                if "verbal memory" in val_str:
                    test_scores["Verbal Memory Test (VBM)"] += 5
                if "visual memory" in val_str:
                    test_scores["Visual Memory Test (VSM)"] += 5
    
    # Return the test with the highest score, if any score is > 0
    max_score = max(test_scores.values()) if test_scores else 0
    if max_score > 0:
        return max(test_scores.items(), key=lambda x: x[1])[0]
    
    return None

def clean_value(val):
    """Clean and convert a value to a number if possible."""
    if pd.isna(val):
        return None
    
    val_str = str(val).strip()
    
    # Remove any text and keep only numbers, decimal points, and minus signs
    # This helps with values like "Score: 42" or "42 (percentile)"
    num_str = re.sub(r'[^0-9.-]', '', val_str)
    
    if not num_str:
        return None
    
    try:
        # Convert to float
        num_val = float(num_str)
        
        # Sanity check for standard scores and percentiles
        # Standard scores are typically between 0-200
        # Percentiles are between 0-100
        if num_val > 200 and num_val < 1000:
            # This might be a reaction time, not a standard score
            return num_val
        elif num_val > 200:
            # This is likely an error, try to fix it
            # Sometimes digits get concatenated incorrectly
            if len(num_str) > 3:
                # Try to split into separate numbers
                if '.' in num_str:
                    # If there's a decimal point, keep it intact
                    parts = num_str.split('.')
                    if len(parts[0]) > 2:
                        # The integer part is too long, probably concatenated
                        return float(parts[0][0:2] + '.' + parts[0][2:] + parts[1])
                else:
                    # No decimal point, try to split at a reasonable point
                    if len(num_str) > 2:
                        return float(num_str[0:2])
            
        return num_val
    except ValueError:
        return None

def process_table(table, expected_tests, flavor, debug=False):
    """Process a single table to extract cognitive test data."""
    extracted_data = []
    df = table.df
    
    if df.empty or df.shape[1] < 2:  # Need at least 2 columns for test name and score
        return []
    
    # Try to identify the test from the table
    current_test = identify_test_in_table(df, expected_tests)
    
    if debug:
        print(f"    Table {table.order} Head:")
        print(df.head(3))
    
    if not current_test:
        if debug:
            print(f"    No test identified for table {table.order}")
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
                if subtest.lower() == val_str.lower() or subtest.lower() in val_str.lower():
                    subtest_rows[subtest] = (i, j)
                    break
    
    # Second pass: extract values for each subtest
    for subtest, (row_idx, col_idx) in subtest_rows.items():
        if debug:
            print(f"      Found subtest '{subtest}' (Test: {current_test}) at row {row_idx}, col {col_idx}")
        
        row = df.iloc[row_idx]
        
        # Look for numeric values in the next few columns
        score, standard, percentile = None, None, None
        
        # Strategy A: Check for values in the same row
        for k in range(col_idx+1, min(col_idx+5, len(row))):
            if k < len(row):
                val_k = row.iloc[k]
                num_val = clean_value(val_k)
                if num_val is not None:
                    if score is None:
                        score = num_val
                        if debug:
                            print(f"        Strat A: Got Score {score} from col {k}")
                    elif standard is None:
                        # Sanity check for standard scores (typically 0-200)
                        if 0 <= num_val <= 200:
                            standard = num_val
                            if debug:
                                print(f"        Strat A: Got Standard {standard} from col {k}")
                    elif percentile is None:
                        # Sanity check for percentiles (0-100)
                        if 0 <= num_val <= 100:
                            percentile = num_val
                            if debug:
                                print(f"        Strat A: Got Percentile {percentile} from col {k}")
                            break
        
        # Strategy B: If we didn't find all values, try looking in the next row at the same positions
        if (score is None or standard is None or percentile is None) and row_idx + 1 < len(df):
            if debug:
                print(f"        Strat A missed values, trying Strat B (Row Below)...")
            
            next_row = df.iloc[row_idx + 1]
            for k in range(max(0, col_idx-1), min(col_idx+5, len(next_row))):
                if k < len(next_row):
                    val_k = next_row.iloc[k]
                    num_val = clean_value(val_k)
                    if num_val is not None:
                        if score is None:
                            score = num_val
                            if debug:
                                print(f"        Strat B: Got Score {score} from next row, col {k}")
                        elif standard is None:
                            # Sanity check for standard scores
                            if 0 <= num_val <= 200:
                                standard = num_val
                                if debug:
                                    print(f"        Strat B: Got Standard {standard} from next row, col {k}")
                        elif percentile is None:
                            # Sanity check for percentiles
                            if 0 <= num_val <= 100:
                                percentile = num_val
                                if debug:
                                    print(f"        Strat B: Got Percentile {percentile} from next row, col {k}")
                                break
        
        # Strategy C: For specific tests, look in a wider range
        if (score is None or standard is None or percentile is None):
            # Special handling for tests that might have values in different locations
            if current_test in ["Finger Tapping Test (FTT)", "Four Part Continuous Performance Test"]:
                if debug:
                    print(f"        Trying Strat C (Wide Search) for {current_test}...")
                
                # Look in a wider range of rows and columns
                for r_offset in range(-1, 3):  # Look 1 row up and 2 rows down
                    check_row_idx = row_idx + r_offset
                    if 0 <= check_row_idx < len(df):
                        check_row = df.iloc[check_row_idx]
                        for k in range(len(check_row)):
                            if k != col_idx:  # Skip the column with the subtest name
                                val_k = check_row.iloc[k]
                                num_val = clean_value(val_k)
                                if num_val is not None:
                                    if score is None:
                                        score = num_val
                                        if debug:
                                            print(f"        Strat C: Got Score {score} from row {check_row_idx}, col {k}")
                                    elif standard is None:
                                        # Sanity check for standard scores
                                        if 0 <= num_val <= 200:
                                            standard = num_val
                                            if debug:
                                                print(f"        Strat C: Got Standard {standard} from row {check_row_idx}, col {k}")
                                        else:
                                            if debug:
                                                print(f"        Strat C: Skipping invalid standard score {num_val}")
                                    elif percentile is None:
                                        # Sanity check for percentiles
                                        if 0 <= num_val <= 100:
                                            percentile = num_val
                                            if debug:
                                                print(f"        Strat C: Got Percentile {percentile} from row {check_row_idx}, col {k}")
                                            break
        
        if debug:
            print(f"      >>> Stored for '{subtest}': S={score}, Std={standard}, Pct={percentile}")
        
        if score is not None or standard is not None or percentile is not None:
            extracted_data.append((current_test, subtest, score, standard, percentile, flavor, table.accuracy))
    
    return extracted_data

def extract_subtests_from_pdf(pdf_path, patient_id=None, debug=False):
    """Extract cognitive subtests from a PDF report using camelot."""
    if patient_id is None:
        # Try to extract patient ID from filename
        base_name = os.path.basename(pdf_path)
        patient_match = re.match(r'^(\d+)', base_name)
        if patient_match:
            patient_id = patient_match.group(1)
        else:
            patient_id = "unknown"
    
    if debug:
        print(f"\nStarting extraction from {pdf_path}...")
    
    all_results = []
    found_items = set()  # Track found test-subtest combinations to avoid duplicates
    
    # Define the expected tests
    expected_tests = list(known_subtests_dict.keys())
    
    # Process each page of the PDF
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get the number of pages
            with open(pdf_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                num_pages = len(pdf.pages)
            
            # Process each page
            for page_num in range(1, num_pages + 1):
                if debug:
                    print(f"\nProcessing page {page_num}...")
                
                # Try different flavors (lattice and stream)
                for flavor in ['lattice', 'stream']:
                    if debug:
                        print(f"\n  Trying flavor: '{flavor}' on Page {page_num}")
                    
                    tables = camelot.read_pdf(
                        pdf_path,
                        pages=str(page_num),
                        flavor=flavor,
                        copy_text=['v'],
                        strip_text='\n',
                        line_scale=40,
                        split_text=True,
                        flag_size=True,
                        layout_kwargs={'detect_vertical': True},
                        suppress_stdout=not debug
                    )
                    
                    if len(tables) > 0:
                        if debug:
                            print(f"    Found {len(tables)} tables with flavor '{flavor}'.")
                        
                        # Process each table
                        for table in tables:
                            # Skip tables with very low accuracy
                            if table.accuracy < 80:
                                if debug:
                                    print(f"    Skipping table {table.order} (Flavor: {flavor}) - low accuracy: {table.accuracy:.2f}%")
                                continue
                            
                            # Check if this table is a duplicate of one we've already processed
                            table_hash = hash(str(table.df.values.tolist()))
                            if table_hash in [hash(str(t.df.values.tolist())) for t in tables[:table.order-1]]:
                                if debug:
                                    print(f"    Skipping table {table.order} (Flavor: {flavor}) - duplicate content already processed.")
                                continue
                            
                            # Process the table
                            results = process_table(table, expected_tests, flavor, debug)
                            
                            # Add new items to the results
                            new_items_count = 0
                            for result in results:
                                test, subtest = result[0], result[1]
                                key = (test, subtest)
                                
                                # Check if we already have this test-subtest combination
                                if key not in found_items:
                                    all_results.append((patient_id,) + result)
                                    found_items.add(key)
                                    new_items_count += 1
                                else:
                                    # If we already have this test-subtest, check if the new one has better accuracy
                                    existing_idx = next((i for i, r in enumerate(all_results) 
                                                        if r[1] == test and r[2] == subtest), None)
                                    
                                    if existing_idx is not None:
                                        existing_accuracy = all_results[existing_idx][7]
                                        new_accuracy = result[6]
                                        
                                        if new_accuracy > existing_accuracy:
                                            if debug:
                                                print(f"      Replaced ({test}, {subtest}) with higher accuracy entry (Acc: {new_accuracy:.1f} > {existing_accuracy:.1f})")
                                            all_results[existing_idx] = (patient_id,) + result
                            
                            if debug and new_items_count > 0:
                                print(f"      Added {new_items_count} new items from table {table.order}")
    
    except Exception as e:
        if debug:
            print(f"Error extracting data: {str(e)}")
            traceback.print_exc()
    
    # Filter out duplicate entries and keep only the highest accuracy ones
    unique_results = {}
    for result in all_results:
        patient_id, test, subtest = result[0], result[1], result[2]
        key = (patient_id, test, subtest)
        
        if key not in unique_results or result[7] > unique_results[key][7]:
            unique_results[key] = result
    
    # Convert back to list, removing the flavor and accuracy columns
    final_results = [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in unique_results.values()]
    
    return final_results

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
        print(f"Total unique subtest entries extracted: {len(results)}")
        print(f"Extraction time: {end_time - start_time:.2f} seconds")
        
        # Group by test for better readability
        tests = {}
        for result in results:
            test = result[1]
            if test not in tests:
                tests[test] = []
            tests[test].append(result)
        
        for test, items in sorted(tests.items()):
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
    """Function to integrate with cognitive_importer.py"""
    try:
        results = extract_subtests_from_pdf(pdf_path, patient_id, debug=debug)
        if not results:
            if debug:
                print(f"No cognitive subtest data found in {pdf_path}")
            return []

        formatted_results = []
        for pid, test, subtest, raw, std, pct in results:
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
    parser = argparse.ArgumentParser(description="Extract cognitive test data from PDF reports")
    parser.add_argument("pdf_path", help="Path to the PDF file to process")
    parser.add_argument("--patient-id", help="Optional patient ID (default: extracted from filename)")
    parser.add_argument("--output", help="Output CSV file path (default: extracted_cognitive_data_<patient_id>.csv)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    try:
        extract_and_save(args.pdf_path, args.patient_id, args.output, args.debug)
        print(f"Processing {os.path.basename(args.pdf_path)} for patient {args.patient_id or os.path.basename(args.pdf_path).split('.')[0]}...")
    except Exception as e:
        print(f"Error processing {args.pdf_path}: {str(e)}")
        if args.debug:
            traceback.print_exc()
import camelot
import pandas as pd
import numpy as np
import re # For cleaning asterisks
import os
import warnings
import traceback
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
    # Simplified FPCPT - treats subtests globally across parts
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
        
        # Validate the value - reject extreme outliers
        if numeric_val < -100 or numeric_val > 1000:
            print(f"Warning: Extreme value detected: {numeric_val}. Ignoring.")
            return None
            
        return float(numeric_val)
    except Exception as e:
        print(f"Error cleaning value '{value}': {str(e)}")
        return None


def identify_table_test(df, expected_tests_for_page):
    """Identifies which main test a table likely belongs to."""
    if df.empty or df.shape[1] < 1:
        return None
    
    possible_matches = {}
    
    # Extract all values from the table for better matching
    all_values = []
    for col in range(df.shape[1]):
        for val in df.iloc[:, col]:
            if val is not None and not pd.isna(val):
                all_values.append(str(val).strip())
    
    print(f"DEBUG: Table values sample: {all_values[:5]}...")
    
    # Check for matches with known subtests
    for main_test_name in expected_tests_for_page:
        count = 0
        expected_subs = known_subtests_dict.get(main_test_name, [])
        
        # Check for subtest matches
        for value in all_values:
            # Check for exact match
            if value in expected_subs:
                count += 1
                continue
                
            # Check for partial match
            for subtest in expected_subs:
                if subtest in value:
                    count += 1
                    break
            
            # Check for test name in value
            if main_test_name in value:
                count += 2  # Give more weight to test name matches
        
        if count > 0:
            possible_matches[main_test_name] = count
            print(f"DEBUG: Found {count} matches for {main_test_name}")

    if not possible_matches:
        # Special check for FPCPT
        if "Four Part Continuous Performance Test" in expected_tests_for_page:
            for value in all_values:
                if re.search(r"Part\s+\d+|FPCPT|Four Part", value):
                    return "Four Part Continuous Performance Test"
        return None

    # Return the test with the most matches
    return max(possible_matches, key=possible_matches.get)


def extract_subtests_from_pdf(pdf_path, patient_id=None):
    """Extract cognitive subtests from a PDF report using camelot."""
    all_results = {}
    
    print(f"Starting extraction from {pdf_path}...")
    
    # Define specific table areas for each page based on known PDF structure
    # Format: [page_num, flavor, [top, left, bottom, right]]
    table_areas = [
        # Page 1 tables
        [1, 'lattice', [200, 50, 400, 550]],  # Upper section
        [1, 'lattice', [400, 50, 700, 550]],  # Lower section
        
        # Page 2 tables
        [2, 'lattice', [100, 50, 350, 550]],  # Upper section
        [2, 'lattice', [350, 50, 700, 550]],  # Lower section
        
        # Page 3 tables
        [3, 'lattice', [100, 50, 700, 550]],  # Full page
    ]
    
    # Process each defined table area
    for page_num, flavor, area in table_areas:
        print(f"\nProcessing Page {page_num}, Area: {area}...")
        
        try:
            # Try extraction with the specified area
            print(f"  Trying {flavor} mode with defined area...")
            tables = camelot.read_pdf(
                pdf_path, 
                pages=str(page_num),
                flavor=flavor,
                table_areas=[','.join(map(str, area))],
                line_scale=40,  # Increase line scale to detect more lines
                process_background=True  # Process background lines
            )
            
            if len(tables) == 0:
                # If lattice fails, try stream mode
                print("  No tables found with lattice, trying stream mode...")
                tables = camelot.read_pdf(
                    pdf_path, 
                    pages=str(page_num),
                    flavor='stream',
                    table_areas=[','.join(map(str, area))],
                    edge_tol=500,  # Higher tolerance for edges
                    row_tol=10  # Higher tolerance for rows
                )
            
            print(f"  Found {len(tables)} table(s)")
            
            expected_tests = tests_on_page.get(page_num, [])
            
            # Process each table
            for i, table in enumerate(tables):
                df = table.df
                
                # Skip empty tables
                if df.empty:
                    print(f"  Table {i+1} is empty, skipping")
                    continue
                
                print(f"\n  Table {i+1} shape: {df.shape}")
                print(f"  Table accuracy: {table.accuracy}")
                print("  Table content sample:")
                print(df.head(3))
                
                # Try to identify which test this table belongs to
                test_name = identify_table_test(df, expected_tests)
                
                if test_name:
                    print(f"  Table {i+1} identified as: {test_name}")
                    expected_subtests = known_subtests_dict.get(test_name, [])
                    
                    # Try to identify the structure of the table
                    # Look for column headers or patterns in the data
                    col_indices = {}
                    
                    # First, search for column headers
                    for row_idx in range(min(5, len(df))):
                        for col_idx in range(df.shape[1]):
                            cell_value = str(df.iloc[row_idx, col_idx]).lower()
                            if any(keyword in cell_value for keyword in ["test", "subtest", "metric"]):
                                col_indices['subtest'] = col_idx
                            elif any(keyword in cell_value for keyword in ["raw", "score"]):
                                col_indices['score'] = col_idx
                            elif any(keyword in cell_value for keyword in ["standard", "std"]):
                                col_indices['standard'] = col_idx
                            elif any(keyword in cell_value for keyword in ["percentile", "%ile"]):
                                col_indices['percentile'] = col_idx
                    
                    # If we couldn't identify columns by headers, use default positions
                    if 'subtest' not in col_indices:
                        # Try to find the column with subtest names by matching with expected subtests
                        for col_idx in range(df.shape[1]):
                            matches = 0
                            for row_idx in range(len(df)):
                                cell_value = str(df.iloc[row_idx, col_idx])
                                for subtest in expected_subtests:
                                    if subtest in cell_value:
                                        matches += 1
                            if matches > 0:
                                col_indices['subtest'] = col_idx
                                break
                        
                        # If still not found, use default
                        if 'subtest' not in col_indices:
                            col_indices['subtest'] = 0
                    
                    # Set defaults for other columns if not found
                    if 'score' not in col_indices and df.shape[1] > 1:
                        col_indices['score'] = 1
                    if 'standard' not in col_indices and df.shape[1] > 2:
                        col_indices['standard'] = 2
                    if 'percentile' not in col_indices and df.shape[1] > 3:
                        col_indices['percentile'] = 3
                    
                    print(f"  Using columns: {col_indices}")
                    
                    # Handle Four Part CPT special case
                    current_part = None
                    is_fpcpt = (test_name == "Four Part Continuous Performance Test")
                    
                    # Skip the header row(s)
                    start_row = 0
                    for i in range(min(5, len(df))):
                        if any(keyword in str(df.iloc[i]).lower() for keyword in ["raw", "score", "standard", "percentile"]):
                            start_row = i + 1
                            break
                    
                    # Process each row
                    for row_idx in range(start_row, len(df)):
                        # Skip rows with all empty cells
                        if df.iloc[row_idx].isna().all():
                            continue
                            
                        # Get subtest name
                        col_subtest = col_indices.get('subtest')
                        if col_subtest is None or col_subtest >= df.shape[1]:
                            continue
                            
                        subtest_name = str(df.iloc[row_idx, col_subtest]).strip()
                        if not subtest_name:
                            continue
                        
                        # Check for FPCPT part headers
                        if is_fpcpt and re.search(r"Part\s+\d+", subtest_name):
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
                                
                                col_score = col_indices.get('score')
                                if col_score is not None and col_score < df.shape[1]:
                                    score = clean_value(df.iloc[row_idx, col_score])
                                
                                col_standard = col_indices.get('standard')
                                if col_standard is not None and col_standard < df.shape[1]:
                                    standard = clean_value(df.iloc[row_idx, col_standard])
                                
                                col_percentile = col_indices.get('percentile')
                                if col_percentile is not None and col_percentile < df.shape[1]:
                                    percentile = clean_value(df.iloc[row_idx, col_percentile])
                                
                                # For FPCPT, add part number
                                if is_fpcpt and current_part:
                                    full_subtest_name = f"{matched_subtest} - {current_part}"
                                else:
                                    full_subtest_name = matched_subtest
                                
                                # Only add if we have at least one valid value
                                if score is not None or standard is not None or percentile is not None:
                                    # Store result
                                    result_key = (test_name, full_subtest_name)
                                    if result_key not in all_results:
                                        all_results[result_key] = {
                                            'Score': score,
                                            'Standard': standard,
                                            'Percentile': percentile
                                        }
                                        print(f"    Extracted: {result_key} -> Score: {score}, Standard: {standard}, Percentile: {percentile}")
                            except Exception as e:
                                print(f"    Error extracting values for {subtest_name}: {str(e)}")
                else:
                    print(f"  Could not identify test for table {i+1}")
        
        except Exception as e:
            print(f"  Error processing page {page_num}, area {area}: {str(e)}")
            traceback.print_exc()
    
    # Convert results to database format
    subtests_data = []
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
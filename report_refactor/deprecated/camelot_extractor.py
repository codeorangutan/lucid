import camelot
import pandas as pd
import numpy as np
import re
import os
import glob
import traceback
import warnings
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
    except Exception as e:
        print(f"Error cleaning value '{value}': {str(e)}")
        return None

def extract_tables_from_pdf(pdf_path, output_dir="extracted_tables"):
    """Extract tables from PDF using camelot and save to CSV files."""
    if not os.path.exists(pdf_path):
        print(f"ERROR: File {pdf_path} not found!")
        return False
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Extracting tables from {pdf_path} using Camelot...")
    
    # Process each page
    for page_num in [1, 2, 3]:
        print(f"\nProcessing page {page_num}...")
        
        # Try both flavors
        for flavor in ['lattice', 'stream']:
            try:
                print(f"  Trying {flavor} mode...")
                tables = camelot.read_pdf(
                    pdf_path,
                    pages=str(page_num),
                    flavor=flavor
                )
                
                print(f"  Found {len(tables)} tables with {flavor} mode")
                
                # Save each table to CSV
                for i, table in enumerate(tables):
                    csv_file = os.path.join(output_dir, f"page{page_num}_{flavor}_{i+1}.csv")
                    table.to_csv(csv_file)
                    print(f"  Saved table {i+1} to {csv_file} (Shape: {table.df.shape}, Accuracy: {table.accuracy:.2f}%)")
                
            except Exception as e:
                print(f"  Error with {flavor} mode on page {page_num}: {str(e)}")
                traceback.print_exc()
    
    return True

def process_extracted_csvs(csv_dir="extracted_tables"):
    """Process extracted CSV files to get cognitive test data."""
    # Get all CSV files in the directory
    csv_files = glob.glob(f"{csv_dir}/*.csv")
    
    if not csv_files:
        print(f"No CSV files found in the {csv_dir} directory.")
        return []
    
    all_extracted_data = []
    
    # Process each CSV file
    for csv_file in csv_files:
        try:
            # Read the CSV file
            df = pd.read_csv(csv_file, header=None)
            
            # Print basic info about the CSV
            print(f"\nProcessing {os.path.basename(csv_file)}")
            print(f"  Shape: {df.shape}")
            
            # Find test names in the CSV
            current_test = None
            
            for i, row in df.iterrows():
                row_values = [str(val).strip() for val in row.values if not pd.isna(val) and str(val).strip()]
                if not row_values:
                    continue
                    
                # Check if this row contains a test name
                for test_name in known_subtests_dict.keys():
                    if any(test_name in str(val) for val in row_values):
                        current_test = test_name
                        print(f"  Found test: {current_test}")
                        break
                
                # If we have a current test, check for subtests
                if current_test:
                    expected_subtests = known_subtests_dict.get(current_test, [])
                    
                    for subtest in expected_subtests:
                        # Check if this row contains a subtest (with or without asterisk)
                        subtest_clean = subtest.replace('*', '')
                        subtest_match = False
                        
                        for j, val in enumerate(row.values):
                            if pd.isna(val) or not str(val).strip():
                                continue
                                
                            val_clean = str(val).replace('*', '').strip()
                            
                            if subtest_clean in val_clean:
                                subtest_match = True
                                # Try to extract score, standard, and percentile
                                score = None
                                standard = None
                                percentile = None
                                
                                # Look for numeric values in the next few columns
                                for k in range(j+1, min(j+4, len(row))):
                                    if k < len(row):
                                        val_k = row.iloc[k]
                                        if not pd.isna(val_k) and str(val_k).strip():
                                            # If we haven't found a score yet
                                            if score is None:
                                                score = clean_value(val_k)
                                            # If we have a score but no standard
                                            elif standard is None:
                                                standard = clean_value(val_k)
                                            # If we have score and standard but no percentile
                                            elif percentile is None:
                                                percentile = clean_value(val_k)
                                
                                if score is not None or standard is not None or percentile is not None:
                                    all_extracted_data.append((current_test, subtest, score, standard, percentile))
                                    print(f"    Found subtest: {subtest} -> Score: {score}, Standard: {standard}, Percentile: {percentile}")
                                
                                break
        
        except Exception as e:
            print(f"Error processing {csv_file}: {str(e)}")
    
    # Process and deduplicate the data
    processed_data = process_and_deduplicate(all_extracted_data)
    
    return processed_data

def process_and_deduplicate(extracted_data):
    """Process and deduplicate the extracted data, prioritizing complete entries."""
    # Group by test and subtest
    grouped_data = {}
    for test, subtest, score, standard, percentile in extracted_data:
        key = (test, subtest)
        if key not in grouped_data:
            grouped_data[key] = []
        grouped_data[key].append((score, standard, percentile))
    
    # Select the best entry for each test/subtest
    final_data = []
    for (test, subtest), entries in grouped_data.items():
        # Sort by completeness (number of non-None values)
        sorted_entries = sorted(
            entries,
            key=lambda x: (
                sum(1 for v in x if v is not None),  # Count non-None values
                0 if x[0] is None else 1,  # Prioritize entries with score
                0 if x[1] is None else 1,  # Prioritize entries with standard
                0 if x[2] is None else 1   # Prioritize entries with percentile
            ),
            reverse=True  # Most complete first
        )
        
        # Take the most complete entry
        best_entry = sorted_entries[0]
        final_data.append((test, subtest, best_entry[0], best_entry[1], best_entry[2]))
    
    return final_data

def extract_subtests_from_pdf(pdf_path, patient_id=None):
    """Extract cognitive subtests from a PDF report using camelot."""
    print(f"Starting extraction from {pdf_path}...")
    
    # Step 1: Extract tables from PDF
    output_dir = "extracted_tables"
    if not extract_tables_from_pdf(pdf_path, output_dir):
        return []
    
    # Step 2: Process the extracted CSV files
    extracted_data = process_extracted_csvs(output_dir)
    
    # Step 3: Convert to database format
    subtests_data = []
    for test_name, metric, score, standard, percentile in extracted_data:
        subtests_data.append((
            patient_id,
            test_name,
            metric,
            score,
            standard,
            percentile
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
        
        # Save to CSV for verification
        output_df = pd.DataFrame(
            results, 
            columns=["PatientID", "Test", "Subtest", "Score", "Standard", "Percentile"]
        )
        output_df.to_csv("extracted_cognitive_data_final.csv", index=False)
        print(f"\nExtracted data saved to extracted_cognitive_data_final.csv")

import os
import pandas as pd
import re
import glob

def clean_value(value):
    """Clean and convert a value to numeric, removing asterisks."""
    if value is None or pd.isna(value) or value == '':
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

def extract_test_data_from_csv(csv_path):
    """Extract cognitive test data from a CSV file."""
    try:
        # Read the CSV file
        df = pd.read_csv(csv_path, header=None)
        
        # Print basic info about the CSV
        print(f"\nProcessing {os.path.basename(csv_path)}")
        print(f"  Shape: {df.shape}")
        
        # Define known test names to look for
        known_tests = [
            "Verbal Memory Test (VBM)",
            "Visual Memory Test (VSM)",
            "Finger Tapping Test (FTT)",
            "Symbol Digit Coding (SDC)",
            "Stroop Test (ST)",
            "Shifting Attention Test (SAT)",
            "Continuous Performance Test (CPT)",
            "Reasoning Test (RT)",
            "Four Part Continuous Performance Test"
        ]
        
        # Define known subtests for each test
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
        
        # Find test names in the CSV
        current_test = None
        extracted_data = []
        
        for i, row in df.iterrows():
            row_values = [str(val).strip() for val in row.values if not pd.isna(val) and str(val).strip()]
            if not row_values:
                continue
                
            # Check if this row contains a test name
            for test_name in known_tests:
                if any(test_name in str(val) for val in row_values):
                    current_test = test_name
                    print(f"  Found test: {current_test}")
                    break
            
            # If we have a current test, check for subtests
            if current_test:
                expected_subtests = known_subtests_dict.get(current_test, [])
                
                for subtest in expected_subtests:
                    # Check if this row contains a subtest
                    subtest_match = False
                    for j, val in enumerate(row.values):
                        if pd.isna(val) or not str(val).strip():
                            continue
                            
                        if subtest in str(val):
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
                                # Check if we already have this subtest
                                duplicate = False
                                for item in extracted_data:
                                    if item[0] == current_test and item[1] == subtest:
                                        duplicate = True
                                        break
                                
                                if not duplicate:
                                    extracted_data.append((current_test, subtest, score, standard, percentile))
                                    print(f"    Found subtest: {subtest} -> Score: {score}, Standard: {standard}, Percentile: {percentile}")
                            
                            break
        
        return extracted_data
    
    except Exception as e:
        print(f"Error processing {csv_path}: {str(e)}")
        return []

def main():
    # Get all CSV files in the extracted_tables directory
    csv_files = glob.glob("extracted_tables/*.csv")
    
    if not csv_files:
        print("No CSV files found in the extracted_tables directory.")
        return
    
    all_extracted_data = []
    
    # Process each CSV file
    for csv_file in csv_files:
        extracted_data = extract_test_data_from_csv(csv_file)
        all_extracted_data.extend(extracted_data)
    
    # Remove duplicates
    unique_data = []
    for item in all_extracted_data:
        if item not in unique_data:
            unique_data.append(item)
    
    # Print summary
    print("\n" + "="*50)
    print(f"Total unique subtests extracted: {len(unique_data)}")
    print("="*50)
    
    # Group by test
    tests = {}
    for test, subtest, score, standard, percentile in unique_data:
        if test not in tests:
            tests[test] = []
        tests[test].append((subtest, score, standard, percentile))
    
    # Print by test
    for test, subtests in tests.items():
        print(f"\n{test}:")
        for subtest, score, standard, percentile in subtests:
            print(f"  {subtest}: Score={score}, Standard={standard}, Percentile={percentile}")
    
    # Format for database
    patient_id = "40277"  # Hardcoded for this example
    db_format = []
    for test, subtest, score, standard, percentile in unique_data:
        db_format.append((patient_id, test, subtest, score, standard, percentile))
    
    # Save to CSV
    output_df = pd.DataFrame(db_format, columns=["PatientID", "Test", "Subtest", "Score", "Standard", "Percentile"])
    output_df.to_csv("extracted_cognitive_data.csv", index=False)
    print(f"\nExtracted data saved to extracted_cognitive_data.csv")

if __name__ == "__main__":
    main()

import camelot
import pandas as pd
import numpy as np
import re
import traceback # Import traceback for detailed error info
import os

# --- Constants and Setup (Keep as before) ---
known_subtests_dict = {
    "Verbal Memory Test (VBM)": ["Correct Hits - Immediate", "Correct Passes - Immediate", "Correct Hits - Delay", "Correct Passes - Delay"],
    "Visual Memory Test (VSM)": ["Correct Hits - Immediate", "Correct Passes - Immediate", "Correct Hits - Delay", "Correct Passes - Delay"],
    "Finger Tapping Test (FTT)": ["Right Taps Average", "Left Taps Average"],
    "Symbol Digit Coding (SDC)": ["Correct Responses", "Errors*"],
    "Stroop Test (ST)": ["Simple Reaction Time*", "Complex Reaction Time Correct*", "Stroop Reaction Time Correct*", "Stroop Commission Errors*"],
    "Shifting Attention Test (SAT)": ["Correct Responses", "Errors*", "Correct Reaction Time*"],
    "Continuous Performance Test (CPT)": ["Correct Responses", "Omission Errors*", "Commission Errors*", "Choice Reaction Time Correct*"],
    "Reasoning Test (RT)": ["Correct Responses", "Average Correct Reaction Time*", "Commission Errors*", "Omission Errors*"],
    "Four Part Continuous Performance Test": ["Average Correct Reaction Time*", "Correct Responses", "Incorrect Responses*", "Average Incorrect Reaction Time*", "Omission Errors*"]
}

tests_on_page = {
    1: ["Verbal Memory Test (VBM)", "Visual Memory Test (VSM)", "Finger Tapping Test (FTT)"],
    2: ["Symbol Digit Coding (SDC)", "Stroop Test (ST)", "Shifting Attention Test (SAT)", "Continuous Performance Test (CPT)", "Reasoning Test (RT)"],
    3: ["Four Part Continuous Performance Test"]
}

def clean_value(value):
    if value is None: return None
    try:
        cleaned = str(value).replace('*', '').replace('\n', ' ').strip() # Added newline replace
        if not cleaned: return None
        numeric_val = pd.to_numeric(cleaned, errors='coerce')
        if pd.isna(numeric_val): return None
        return float(numeric_val)
    except Exception: return None

def looks_like_numeric(series):
    """Check if a pandas Series looks like it contains mostly numbers."""
    if series.empty: return False
    numeric_count = pd.to_numeric(series.astype(str).str.replace('*','').str.strip(), errors='coerce').notna().sum()
    return numeric_count > len(series) / 2 # Heuristic: More than half look numeric

def identify_table_test(df, expected_tests_for_page):
    if df.empty or df.shape[1] < 1:
        return None

    # *** Debugging Check ***
    first_col_series = df.iloc[:, 0].astype(str).str.strip()
    if looks_like_numeric(first_col_series):
        print(f"    DEBUG: First column appears numeric ({first_col_series.head(3).tolist()}), likely misparsed. Skipping identification for this table.")
        return None # Don't try to identify if the first column looks wrong

    possible_matches = {}
    first_col_values = first_col_series.tolist()

    for main_test_name in expected_tests_for_page:
        count = 0
        expected_subs = known_subtests_dict.get(main_test_name, [])
        for sub_in_table in first_col_values:
            # Be more flexible with matching (strip extra spaces/newlines)
            cleaned_sub_in_table = sub_in_table.replace('\n', ' ').strip()
            if cleaned_sub_in_table in expected_subs:
                count += 1
        if count > 0:
            possible_matches[main_test_name] = count

    if not possible_matches:
        # --- Refined FPCPT Check ---
        if "Four Part Continuous Performance Test" in expected_tests_for_page:
             # Check for "Part X" headers more reliably
             part_header_found = any(re.match(r"Part\s+\d+", item.strip()) for item in first_col_values)
             if part_header_found:
                 print("    DEBUG: Found 'Part X' header, assuming FPCPT.")
                 return "Four Part Continuous Performance Test"

             # Check for FPCPT subtests even without "Part" header explicitly
             count = 0
             expected_subs = known_subtests_dict.get("Four Part Continuous Performance Test", [])
             for sub_in_table in first_col_values:
                 cleaned_sub_in_table = sub_in_table.replace('\n', ' ').strip()
                 if cleaned_sub_in_table in expected_subs:
                     count += 1
             if count > 0:
                  print(f"    DEBUG: Found {count} FPCPT subtests, assuming FPCPT.")
                  return "Four Part Continuous Performance Test"

        print(f"    DEBUG: No known subtests found in first column: {first_col_values[:5]}...") # Show sample
        return None

    best_match = max(possible_matches, key=possible_matches.get)
    return best_match

# --- Main Extraction Logic ---
if __name__ == "__main__":
    pdf_path = '40277.pdf'  # Changed to match your actual file
    all_results = {}
    pages_to_process = [1, 2, 3]
    # *** Explicitly list flavors to try ***
    camelot_flavors_to_try = ['lattice', 'stream']

    print(f"Starting extraction from {pdf_path} using Camelot...")
    print("Ensure Ghostscript is installed and accessible in your system PATH.")
    print("-" * 30)

    if not os.path.exists(pdf_path):
        print(f"ERROR: File {pdf_path} not found!")
    else:
        for page_num in pages_to_process:
            print(f"\n===== PROCESSING PAGE {page_num} =====")
            expected_tests = tests_on_page.get(page_num, [])
            page_processed_successfully = False

            for flavor in camelot_flavors_to_try:
                if page_processed_successfully: break # If lattice worked, maybe skip stream for this page
                print(f"\n--- Trying Flavor: '{flavor}' on Page {page_num} ---")
                try:
                    # Extract tables using Camelot
                    tables = camelot.read_pdf(
                        pdf_path,
                        pages=str(page_num),
                        flavor=flavor,
                        # Optional parameters to try tuning if needed:
                        # stream: edge_tol=50, column_separators=None
                        # lattice: line_scale=40, copy_text=['v'], shift_text=['r','v'], line_tol=2
                        strip_text='\n' # Helps clean up cells with newlines
                    )

                    if not tables or tables.n == 0:
                        print(f"  No tables found by Camelot with flavor '{flavor}'.")
                        continue

                    print(f"  Found {tables.n} table(s) with flavor '{flavor}'.")

                    for i, table in enumerate(tables):
                        df = table.df
                        print(f"\n  --- Analyzing Table {i+1}/{tables.n} (Flavor: {flavor}, Page: {page_num}) ---")
                        print(f"  Accuracy: {table.accuracy:.2f}%, Whitespace: {table.whitespace:.2f}%")
                        print(f"  Raw Table Shape: {df.shape}")
                        print(f"  Raw Table Head:\n{df.head(5).to_string()}") # Print head for inspection
                        print("-" * 20)


                        if df.empty:
                            print("  Skipping empty table.")
                            continue

                        # **Important Check**: Does it have enough columns?
                        if df.shape[1] < 4:
                            print(f"  Skipping table: Insufficient columns ({df.shape[1]}) detected for subtest data. Likely parsing error.")
                            continue

                        # Try to identify the test associated with this table
                        identified_main_test = identify_table_test(df, expected_tests)

                        if identified_main_test:
                            print(f"  SUCCESS: Table identified as: {identified_main_test}")
                            page_processed_successfully = True # Mark page as successfully processed with this flavor
                            expected_subtests_for_this_test = known_subtests_dict.get(identified_main_test, [])

                            # Define column indices (re-evaluate if Camelot behaves differently)
                            col_subtest = 0
                            col_score = 1
                            col_standard = 2
                            col_percentile = 3

                            current_part = None
                            is_fpcpt = (identified_main_test == "Four Part Continuous Performance Test")

                            for row_idx, row in df.iterrows():
                                try:
                                    subtest_name_raw = row.iloc[col_subtest]
                                    if pd.isna(subtest_name_raw) or not str(subtest_name_raw).strip():
                                        continue # Skip empty cells
                                    subtest_name = str(subtest_name_raw).replace('\n', ' ').strip()

                                    if is_fpcpt and re.match(r"Part\s+\d+", subtest_name):
                                        current_part = subtest_name
                                        print(f"      Entering FPCPT {current_part}")
                                        continue

                                    if subtest_name in expected_subtests_for_this_test:
                                        if len(row) > col_percentile: # Ensure row has enough columns
                                            score = clean_value(row.iloc[col_score])
                                            standard = clean_value(row.iloc[col_standard])
                                            percentile = clean_value(row.iloc[col_percentile])

                                            result_key = (identified_main_test, subtest_name)
                                            # Prevent overwriting if found by both lattice and stream (prefer first success)
                                            if result_key not in all_results:
                                                all_results[result_key] = {
                                                    'Score': score, 'Standard': standard, 'Percentile': percentile,
                                                    'Page': page_num, 'Flavor': flavor
                                                }
                                                print(f"      Extracted: {result_key} -> Score: {score}, Standard: {standard}, Percentile: {percentile}")
                                            else:
                                                print(f"      Skipped (already extracted): {result_key}")

                                        else:
                                            print(f"      WARN: Row {row_idx} for '{subtest_name}' has only {len(row)} columns, expected >{col_percentile}.")

                                except Exception as e:
                                    print(f"      ERROR processing row {row_idx} in {identified_main_test}: {e}")
                                    print(f"      Row data: {row.tolist()}")
                        else:
                            print(f"  INFO: Table {i+1} (Flavor: {flavor}, Page: {page_num}) could not be matched to a known test structure based on first column content.")

                except Exception as e:
                    print(f"  CRITICAL ERROR processing page {page_num} with flavor '{flavor}': {e}")
                    print("  Traceback:")
                    traceback.print_exc() # Print full traceback
                    print("-" * 20)


        # --- Final Output ---
        print("\n" + "="*20 + " EXTRACTION COMPLETE " + "="*20)
        if all_results:
            print("\nSuccessfully Extracted Data:")
            # Sort results for readability
            sorted_keys = sorted(all_results.keys(), key=lambda x: (x[0], known_subtests_dict.get(x[0], []).index(x[1]) if x[1] in known_subtests_dict.get(x[0], []) else -1))
            for key in sorted_keys:
                value = all_results[key]
                print(f"  Test: {key[0]}, Subtest: {key[1]}")
                print(f"    Score: {value['Score']}, Standard: {value['Standard']}, Percentile: {value['Percentile']} (Page: {value['Page']}, Flavor: {value['Flavor']})")
        else:
            print("\nNo data extracted successfully. Review the DEBUG/INFO/ERROR messages above.")
            print("Possible next steps:")
            print("  1. Verify Ghostscript installation and PATH.")
            print("  2. Examine the printed 'Raw Table Head' outputs - do they look like tables?")
            print("  3. If 'lattice' finds tables but they look wrong, try tuning 'line_scale' or 'line_tol'.")
            print("  4. If 'stream' finds tables but shape is wrong (e.g., Nx1), try tuning 'edge_tol' or providing 'column_separators'.")
            print("  5. Check the PDF itself for unusual formatting.")

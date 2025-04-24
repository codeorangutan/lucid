import tabula
import pandas as pd
import numpy as np
import io
import re # For cleaning asterisks

# Define the structure of known tests and their subtests
# Using a dictionary for easier lookup
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
    if value is None:
        return None
    try:
        # Remove asterisks, strip whitespace, handle potential non-string types
        cleaned = str(value).replace('*', '').strip()
        if not cleaned: # Handle empty strings after cleaning
             return None
        # Convert to numeric, coerce errors to NaN
        numeric_val = pd.to_numeric(cleaned, errors='coerce')
        # Return None if NaN, otherwise return the number (int if possible)
        if pd.isna(numeric_val):
            return None
        # Return as int if it's a whole number, else float
        # return int(numeric_val) if numeric_val == int(numeric_val) else float(numeric_val)
        # Let's return float consistently for simplicity unless specific int needed
        return float(numeric_val)
    except Exception:
        return None


def identify_table_test(df, expected_tests_for_page):
    """Identifies which main test a table likely belongs to."""
    if df.empty or df.shape[1] < 1:
        return None

    possible_matches = {} # Store counts of matching subtests for each main test

    # Check the first column for known subtest names
    first_col_values = df.iloc[:, 0].astype(str).str.strip().tolist()

    for main_test_name in expected_tests_for_page:
        count = 0
        expected_subs = known_subtests_dict.get(main_test_name, [])
        for sub_in_table in first_col_values:
            # Need exact match here usually
            if sub_in_table in expected_subs:
                count += 1
        if count > 0:
            possible_matches[main_test_name] = count

    # Determine the best match (most subtest matches)
    if not possible_matches:
        # Special check for FPCPT parts which might confuse simple check
        if "Four Part Continuous Performance Test" in expected_tests_for_page:
            for item in first_col_values:
                 # Check if "Part X" structure exists
                 if re.match(r"Part\s+\d+", item):
                      return "Four Part Continuous Performance Test"
            # Check again for FPCPT subtests even if no "Part" header found
            count = 0
            expected_subs = known_subtests_dict.get("Four Part Continuous Performance Test", [])
            for sub_in_table in first_col_values:
                if sub_in_table in expected_subs:
                    count += 1
            if count > 0:
                 return "Four Part Continuous Performance Test"

        return None # No known subtests found

    # Return the test name with the highest count of matching subtests
    best_match = max(possible_matches, key=possible_matches.get)
    return best_match


# --- Main Extraction Logic ---
pdf_path = 'report.pdf' # Make sure this matches your PDF file name
all_results = {}
pages_to_process = [1, 2, 3] # Pages containing the relevant tables

print(f"Starting extraction from {pdf_path}...")

for page_num in pages_to_process:
    print(f"\nProcessing Page {page_num}...")
    try:
        # Extract tables from the current page
        # stream=True often works better for tables without clear lines
        # guess=False can sometimes be more reliable if stream/lattice is specified
        dfs = tabula.read_pdf(pdf_path, pages=str(page_num), multiple_tables=True, stream=True, guess=False, pandas_options={'header': None})
        # Try lattice if stream fails or gives bad results
        # dfs = tabula.read_pdf(pdf_path, pages=str(page_num), multiple_tables=True, lattice=True, guess=False, pandas_options={'header': None})

        if not dfs:
            print(f"  No tables found on page {page_num}.")
            continue

        print(f"  Found {len(dfs)} table(s) on page {page_num}.")

        expected_tests = tests_on_page.get(page_num, [])

        for i, df in enumerate(dfs):
            if df.empty or df.shape[1] < 4: # Need at least Subtest, Score, Standard, Percentile
                print(f"  Skipping empty or narrow table {i+1} on page {page_num}.")
                continue

            # Try to identify which main test this table belongs to
            identified_main_test = identify_table_test(df, expected_tests)

            if identified_main_test:
                print(f"  Table {i+1} identified as: {identified_main_test}")
                expected_subtests_for_this_test = known_subtests_dict.get(identified_main_test, [])

                # Determine column indices (assuming 0=Subtest, 1=Score, 2=Standard, 3=Percentile)
                col_subtest = 0
                col_score = 1
                col_standard = 2
                col_percentile = 3

                # --- Handle Four Part CPT specific structure on Page 3 ---
                # This test interleaves "Part" headers or context rows.
                # The simple extraction below might grab numbers from the wrong rows
                # if not careful. Let's process row by row.
                current_part = None # For potential future use if needed
                is_fpcpt = (identified_main_test == "Four Part Continuous Performance Test")

                for _, row in df.iterrows():
                    # Extract potential subtest name
                    subtest_name_raw = row.iloc[col_subtest]
                    if pd.isna(subtest_name_raw):
                        continue
                    subtest_name = str(subtest_name_raw).strip()

                    # Simple check for FPCPT Part headers
                    if is_fpcpt and re.match(r"Part\s+\d+", subtest_name):
                         current_part = subtest_name # Store part context if needed later
                         # print(f"    Entering {current_part}")
                         continue # Skip the header row itself

                    # Check if this subtest is one we need for the identified main test
                    if subtest_name in expected_subtests_for_this_test:
                        try:
                            score = clean_value(row.iloc[col_score])
                            standard = clean_value(row.iloc[col_standard])
                            percentile = clean_value(row.iloc[col_percentile])

                            result_key = (identified_main_test, subtest_name)
                            all_results[result_key] = {
                                'Score': score,
                                'Standard': standard,
                                'Percentile': percentile,
                                'Page': page_num
                                # 'Part': current_part # Add if needed for FPCPT
                            }
                            print(f"    Extracted: {result_key} -> Score: {score}, Standard: {standard}, Percentile: {percentile}")

                        except IndexError:
                            print(f"    WARN: Row for '{subtest_name}' in {identified_main_test} has fewer columns than expected.")
                        except Exception as e:
                            print(f"    ERROR processing row for {subtest_name} in {identified_main_test}: {e}")
            else:
                 # Optionally print a snippet of tables that weren't identified
                 # print(f"  Table {i+1} could not be matched to a known test structure.")
                 # print(df.head(2).to_string())
                 pass


    except Exception as e:
        print(f"  ERROR processing page {page_num}: {e}")
        import traceback
        traceback.print_exc()


# --- Final Output ---
print("\n--- Extraction Complete ---")
if all_results:
    print("Extracted Data:")
    for key, value in all_results.items():
        print(f"  Test: {key[0]}, Subtest: {key[1]}")
        print(f"    Score: {value['Score']}, Standard: {value['Standard']}, Percentile: {value['Percentile']} (Page: {value['Page']})")
else:
    print("No data extracted. Check PDF path, structure, and tabula settings.")

# Example: Accessing a specific value
# vbm_hits_imm = all_results.get(("Verbal Memory Test (VBM)", "Correct Hits - Immediate"))
# if vbm_hits_imm:
#     print("\nExample Access:")
#     print(f"VBM Correct Hits - Immediate Standard Score: {vbm_hits_imm['Standard']}")
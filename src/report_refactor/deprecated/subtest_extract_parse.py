import re
import json
import os
import sys

def parse_text_file(filename):
    """
    Reads a regular text file and returns its lines.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        print(f"Read {len(lines)} lines from {filename}")
        return lines
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An error occurred reading file '{filename}': {e}", file=sys.stderr)
        return None

# --- Function to Parse Subtest Data from Extracted Lines ---

def parse_subtest_data_from_vbm(lines):
    """
    Parse cognitive subtest data from a list of text lines, starting from VBM.
    Ignores initial metadata and Domain Scores.

    Args:
        lines (list): A list of strings representing the text content.

    Returns:
        dict: A dictionary containing the parsed test data, or an empty dict if no data found.
    """
    if not lines:
        print("Warning: No lines provided to parse.")
        return {}

    results = {}
    current_test = None
    current_data = []
    current_section = None
    parsing_data = False      # Flag: Are we looking for data rows for the current test?
    found_start_test = False  # Flag: Have we found the first test to include (VBM)?

    # --- Regex Patterns ---
    # Match test headers robustly, including known variations
    test_patterns = [
        (re.compile(r"^(Verbal Memory Test(?: \(VBM\))?)", re.IGNORECASE), "Verbal Memory Test (VBM)"),
        (re.compile(r"^(Visual Memory Test(?: \(VSM\))?)", re.IGNORECASE), "Visual Memory Test (VSM)"),
        (re.compile(r"^(Finger Tapping Test(?: \(FTT\))?)", re.IGNORECASE), "Finger Tapping Test (FTT)"),
        (re.compile(r"^(Symbol Digit Coding(?: \(SDC\))?)", re.IGNORECASE), "Symbol Digit Coding Test (SDC)"),
        (re.compile(r"^(Stroop Test(?: \(ST\))?)", re.IGNORECASE), "Stroop Test (ST)"),
        (re.compile(r"^(Shifting Attention Test(?: \(SAT\))?)", re.IGNORECASE), "Shifting Attention Test (SAT)"),
        (re.compile(r"^(Continuous Performance Test(?: \(CPT\))?)", re.IGNORECASE), "Continuous Performance Test (CPT)"),
        (re.compile(r"^(Reasoning Test(?: \(RT\)|NVRT)?)", re.IGNORECASE), "Reasoning Test (RT)"),
        (re.compile(r"^(Four Part Continuous Performance Test(?: \(FPCPT\))?)", re.IGNORECASE), "Four Part Continuous Performance Test (FPCPT)")
    ]
    first_test_name = "Verbal Memory Test (VBM)"

    # Matches data rows: Description text, then 3 numbers/placeholders, optional text after
    # Exclude lines starting like domain scores or purely numeric lines
    data_row_pattern = re.compile(r"^(?!(?:[A-Z][a-z]+ ){1,4}(?:Index|Memory|Speed|Time|Attention|Flexibility|Function)\b)(?![0-9.\s]+$)([^0-9\n\t][^\[\]]{3,}?)\s+(-?\d+(?:\.\d+)?|-|NA)\s+(-?\d+|-|NA)\s+(-?\d+|-|NA)(?:\s*\[DATA ROW\])?(?:\s*$|\s+.*$)")
    # Matches lines that have data *and* description text mixed
    mixed_line_pattern = re.compile(r"^(?!(?:[A-Z][a-z]+ ){1,4}(?:Index|Memory|Speed|Time|Attention|Flexibility|Function)\b)(?![0-9.\s]+$)([^0-9\n\t][^\[\]]{3,}?)\s+(-?\d+(?:\.\d+)?|-|NA)\s+(-?\d+|-|NA)\s+(-?\d+|-|NA)\s*([A-Za-z].*$)")
    # Matches section headers like "Part 1"
    section_pattern = re.compile(r"^(Part\s+(?:[1-4]|ONE|TWO|THREE|FOUR))(?: \[SECTION\])?$", re.IGNORECASE)
    # Matches lines likely starting a description paragraph
    description_start_pattern = re.compile(r"^(?:The\s+)?[A-Z][a-zA-Z\s(),\*]+\s+(?:test|memory|measures|is a|refers to|are in)")

    print(f"\nParsing {len(lines)} lines, starting from '{first_test_name}'...")

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue # Skip empty lines

        # --- State Machine Logic ---

        # 1. Detect Test Headers
        new_test_detected = None
        standardized_test_name = None
        for pattern, name in test_patterns:
            match = pattern.match(line)
            if match:
                new_test_detected = match.group(1).strip() # The matched header text
                standardized_test_name = name            # The canonical name
                break

        if standardized_test_name:
            # Check if this is the first test we are looking for
            if not found_start_test and standardized_test_name == first_test_name:
                found_start_test = True
                print(f"Line {i}: Found starting test: {standardized_test_name}")
            elif not found_start_test:
                continue # Skip headers before the first desired test

            # If we've found the start (or subsequent tests), process the header
            if found_start_test:
                # Save previous test data if any
                if current_test and current_data:
                    results[current_test] = current_data
                    print(f"Saved test: {current_test} with {len(current_data)} data rows")

                # Start new test
                current_test = standardized_test_name
                current_data = []
                current_section = None
                parsing_data = True # Start looking for data for this test
                # print(f"Line {i}: Switched to test: {current_test}") # Less verbose logging
                continue # Move to next line after finding a header

        # If we haven't found the starting test yet, skip all other processing
        if not found_start_test:
            continue

        # --- Process lines only *after* VBM has been found ---

        # 2. Detect Sections within a Test (like FPCPT)
        section_match = section_pattern.match(line)
        # Only apply if we are currently parsing data for the FPCPT test
        if section_match and parsing_data and current_test == "Four Part Continuous Performance Test (FPCPT)":
            current_section = section_match.group(1).upper().replace("ONE", "1").replace("TWO", "2").replace("THREE", "3").replace("FOUR", "4") # Standardize "PART X"
            print(f"Line {i}: Found section: {current_section} for {current_test}")
            continue

        # 3. Detect End of Data Parsing (Description Start)
        # Check this *before* data row patterns if a test context exists
        # Ensure it's not a section header misinterpreted as description
        if parsing_data and current_test and description_start_pattern.match(line) and not section_match:
            # Check if the *previous* line was likely the end of data or header
            if i > 0: # Avoid index error
                 prev_line_strip = lines[i-1].strip()
                 is_prev_data = data_row_pattern.match(prev_line_strip) or mixed_line_pattern.match(prev_line_strip)
                 is_prev_header = False
                 for pattern, _ in test_patterns:
                      if pattern.match(prev_line_strip):
                           is_prev_header = True
                           break

                 if is_prev_data or is_prev_header:
                      print(f"Line {i}: Found description, ending data parsing for {current_test}")
                      parsing_data = False
                      # Don't continue here, the description line itself isn't processed further in this loop

        # 4. Parse Data Rows (only if `parsing_data` is True)
        if parsing_data:
            data_entry = None
            measure = None
            score_str, standard_str, percentile_str = None, None, None
            description_part = None # For mixed lines

            # Remove annotations like [TEST NAME], [SECTION] before matching data
            clean_line = line.replace('[TEST NAME]', '').replace('[SECTION]', '').replace('[DATA ROW]','').strip()

            # Try matching mixed line first
            mixed_match = mixed_line_pattern.match(clean_line)
            if mixed_match:
                measure = mixed_match.group(1).strip()
                score_str = mixed_match.group(2)
                standard_str = mixed_match.group(3)
                percentile_str = mixed_match.group(4)
                description_part = mixed_match.group(5) # Description indicates end of data
            # If not mixed, try matching a standard data row
            elif not description_part:
                data_match = data_row_pattern.match(clean_line)
                if data_match:
                    measure = data_match.group(1).strip()
                    score_str = data_match.group(2)
                    standard_str = data_match.group(3)
                    percentile_str = data_match.group(4)

            # If we found a measure from either pattern
            if measure:
                # Skip common header remnants or irrelevant lines more specificially
                if measure.lower() in ['score', 'standard', 'percentile', 'patient', 'vi**', ''] or measure.startswith("Domain"):
                    continue

                # Convert values safely
                def safe_convert(value_str):
                    if value_str in ['-', 'NA']:
                        return value_str
                    try: 
                        return int(value_str)
                    except ValueError:
                        try: return float(value_str)
                        except ValueError: return value_str

                score = safe_convert(score_str)
                standard = safe_convert(standard_str)
                percentile = safe_convert(percentile_str)

                data_entry = {
                    "Measure": measure,
                    "Score": score,
                    "Standard": standard,
                    "Percentile": percentile
                }

                # Add section if applicable (mainly for FPCPT)
                if current_section and current_test == "Four Part Continuous Performance Test (FPCPT)":
                    data_entry["Section"] = current_section

                # Prevent adding duplicates if regex matches slightly differently on reruns
                is_duplicate = False
                if current_data:
                     last_entry = current_data[-1]
                     if last_entry['Measure'] == data_entry['Measure'] and last_entry.get('Section') == data_entry.get('Section'):
                          # Very basic check, might need refinement if measures can repeat legitimately
                          is_duplicate = True

                if not is_duplicate:
                    current_data.append(data_entry)
                    print(f"Line {i}: Added data row: {measure}")

                    # If description was found on this line, stop parsing data for this test
                    if description_part:
                        print(f"Line {i}: Found description within data line, ending data parsing for {current_test}")
                        parsing_data = False
                        continue


    # --- End of Loop ---

    # Save the last test's data, but only if we started parsing (found VBM)
    if found_start_test and current_test and current_data:
        results[current_test] = current_data
        print(f"Saved final test: {current_test} with {len(current_data)} data rows")
    elif found_start_test and current_test and not current_data:
         print(f"Warning: Last test detected '{current_test}' had no data rows parsed.")

    if not results:
         print(f"Warning: No subtest data found starting from '{first_test_name}'.")

    return results

# --- Main Execution Logic ---

def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {os.path.basename(__file__)} <text_file.txt>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)

    # Parse the text file
    lines = parse_text_file(input_file)

    if lines is None:
        print("Failed to read text file. Exiting.")
        sys.exit(1)

    # Parse the lines, starting from VBM
    results = parse_subtest_data_from_vbm(lines)

    # Save results to JSON
    os.makedirs('parser', exist_ok=True)
    output_filename = os.path.basename(input_file).replace('.txt', '_subtests_parsed.json')
    output_file = os.path.join('parser', output_filename)

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nParsed subtest data saved to: {output_file}")
    except Exception as e:
        print(f"Error saving results to JSON: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
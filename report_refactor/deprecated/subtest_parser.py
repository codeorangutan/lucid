import re
import json
import os
import sys

def parse_text_file(file_path):
    """
    Parse cognitive test data from a text file using a simple line-by-line approach.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {}

    results = {}
    current_test = None
    current_data = []
    current_section = None
    parsing_data = False
    in_domain_scores = False
    
    # Simple patterns
    test_pattern = re.compile(r"^(.*?(?:Test|Index)\s+\([A-Z]{2,5}\))\s*(?:Score\s+Standard\s+Percentile)?(?:\s*Possibly Invalid)?$")
    data_row_pattern = re.compile(r"^([^0-9\n]{3,}?)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)(?:\s*$|\s+.*$)")
    mixed_line_pattern = re.compile(r"^([^0-9\n]{3,}?)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)([A-Za-z].*$)")
    section_pattern = re.compile(r"^Part\s+\d+$")
    domain_scores_pattern = re.compile(r"^Domain\s+ScoresPatient")
    domain_end_pattern = re.compile(r"^VI\*\* - Validity Indicator:")
    description_pattern = re.compile(r"^(?:The\s+)?[A-Za-z]+\s+(?:test|memory|measures|is a)")
    
    # Known test names to handle special cases
    known_tests = {
        "Symbol Digit Coding Test (SDC)": "Symbol Digit Coding Test (SDC)",
        "Symbol Digit Coding (SDC)": "Symbol Digit Coding Test (SDC)",
        "Stroop Test (ST)": "Stroop Test (ST)",
        "Shifting Attention Test (SAT)": "Shifting Attention Test (SAT)",
        "Continuous Performance Test (CPT)": "Continuous Performance Test (CPT)",
        "Four Part Continuous Performance Test (FPCPT)": "Four Part Continuous Performance Test (FPCPT)"
    }
    
    print(f"\nProcessing file: {file_path}")
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Skip page markers
        if line.startswith("=== PAGE"):
            continue
            
        # Handle domain scores section (skip it)
        if domain_scores_pattern.search(line):
            in_domain_scores = True
            print(f"Line {i}: Entering domain scores section")
            continue
            
        if in_domain_scores:
            if domain_end_pattern.search(line):
                in_domain_scores = False
                print(f"Line {i}: Exiting domain scores section")
            continue
        
        # Check for test headers
        test_match = test_pattern.match(line)
        if test_match:
            # Save previous test data if any
            if current_test and current_data:
                results[current_test] = current_data
                print(f"Saved test: {current_test} with {len(current_data)} data rows")
            
            # Start new test
            test_name = test_match.group(1).strip()
            
            # Check if this is a known test (handle special cases)
            for known_test in known_tests:
                if known_test in test_name:
                    test_name = known_test
                    break
                    
            current_test = test_name
            current_data = []
            current_section = None
            parsing_data = True
            print(f"Line {i}: Found test: {current_test}")
            continue
        
        # Special case for SDC test which sometimes doesn't match the pattern
        if "Symbol Digit Coding" in line and "(SDC)" in line:
            if current_test and current_data:
                results[current_test] = current_data
                print(f"Saved test: {current_test} with {len(current_data)} data rows")
            
            current_test = "Symbol Digit Coding Test (SDC)"
            current_data = []
            current_section = None
            parsing_data = True
            print(f"Line {i}: Found test (special case): {current_test}")
            continue
        
        # Check for section headers (like Part 1, Part 2)
        section_match = section_pattern.match(line)
        if section_match and parsing_data:
            current_section = line.strip()
            print(f"Line {i}: Found section: {current_section}")
            continue
        
        # Check for data rows
        if parsing_data:
            # First check if the line contains both data and description
            mixed_match = mixed_line_pattern.match(line)
            if mixed_match:
                measure = mixed_match.group(1).strip()
                score_str = mixed_match.group(2)
                standard_str = mixed_match.group(3)
                percentile_str = mixed_match.group(4)
                description_part = mixed_match.group(5)
                
                # Skip if measure looks like a header
                if measure.lower() in ['score', 'standard', 'percentile']:
                    continue
                
                # Convert values safely
                try: score = int(score_str) if score_str not in ['-', 'NA'] else score_str
                except ValueError: score = score_str
                try: standard = int(standard_str) if standard_str not in ['-', 'NA'] else standard_str
                except ValueError: standard = standard_str
                try: percentile = int(percentile_str) if percentile_str not in ['-', 'NA'] else percentile_str
                except ValueError: percentile = percentile_str
                
                data_entry = {
                    "Measure": measure,
                    "Score": score,
                    "Standard": standard,
                    "Percentile": percentile
                }
                
                if current_section:
                    data_entry["Section"] = current_section
                
                # Check if this measure belongs to the current test
                if current_test == "Finger Tapping Test (FTT)" and "SDC" in measure:
                    print(f"Line {i}: Skipping {measure} as it likely belongs to SDC, not FTT")
                    continue
                
                current_data.append(data_entry)
                print(f"Line {i}: Added data row (from mixed line): {measure}")
                
                # End data parsing since we've found a description
                parsing_data = False
                print(f"Line {i}: Found description after data, ending data parsing for {current_test}")
                continue
                
            # Check if this line looks like a description (which ends data parsing)
            if description_pattern.match(line):
                parsing_data = False
                print(f"Line {i}: Found description, ending data parsing for {current_test}")
                continue
                
            # Try to parse as data row
            data_match = data_row_pattern.match(line)
            if data_match:
                measure = data_match.group(1).strip()
                score_str = data_match.group(2)
                standard_str = data_match.group(3)
                percentile_str = data_match.group(4)
                
                # Skip if measure looks like a header
                if measure.lower() in ['score', 'standard', 'percentile']:
                    continue
                
                # Convert values safely
                try: score = int(score_str) if score_str not in ['-', 'NA'] else score_str
                except ValueError: score = score_str
                try: standard = int(standard_str) if standard_str not in ['-', 'NA'] else standard_str
                except ValueError: standard = standard_str
                try: percentile = int(percentile_str) if percentile_str not in ['-', 'NA'] else percentile_str
                except ValueError: percentile = percentile_str
                
                data_entry = {
                    "Measure": measure,
                    "Score": score,
                    "Standard": standard,
                    "Percentile": percentile
                }
                
                if current_section:
                    data_entry["Section"] = current_section
                
                # Check if this measure belongs to the current test
                # For example, if we're in FTT but see an SDC measure, it's likely a parsing error
                if current_test == "Finger Tapping Test (FTT)" and "SDC" in measure:
                    print(f"Line {i}: Skipping {measure} as it likely belongs to SDC, not FTT")
                    continue
                
                current_data.append(data_entry)
                print(f"Line {i}: Added data row: {measure}")
    
    # Save the last test's data
    if current_test and current_data:
        results[current_test] = current_data
        print(f"Saved test: {current_test} with {len(current_data)} data rows")
    
    # Post-processing to ensure we have all expected measures for certain tests
    # This helps catch cases where the parser might have missed some rows
    expected_measures = {
        "Verbal Memory Test (VBM)": ["Correct Hits - Immediate", "Correct Passes - Immediate", "Correct Hits - Delay", "Correct Passes - Delay"],
        "Visual Memory Test (VSM)": ["Correct Hits - Immediate", "Correct Passes - Immediate", "Correct Hits - Delay", "Correct Passes - Delay"],
        "Symbol Digit Coding Test (SDC)": ["Correct Responses", "Errors*"],
        "Stroop Test (ST)": ["Simple Reaction Time*", "Complex Reaction Time Correct*", "Stroop Reaction Time Correct*", "Stroop Commission Errors*"],
        "Shifting Attention Test (SAT)": ["Correct Responses", "Errors*", "Correct Reaction Time*"],
        "Continuous Performance Test (CPT)": ["Correct Responses", "Omission Errors*", "Commission Errors*", "Choice Reaction Time Correct*"],
        "Reasoning Test (RT)": ["Correct Responses", "Average Correct Reaction Time*", "Commission Errors*", "Omission Errors*"]
    }
    
    # Special handling for FPCPT test which has multiple parts
    fpcpt_expected = {
        "Part 1": ["Average Correct Reaction Time*"],
        "Part 2": ["Correct Responses", "Average Correct Reaction Time*", "Incorrect Responses*", "Average Incorrect Reaction Time*", "Omission Errors*"],
        "Part 3": ["Correct Responses", "Average Correct Reaction Time*", "Incorrect Responses*", "Average Incorrect Reaction Time*", "Omission Errors*"],
        "Part 4": ["Correct Responses", "Average Correct Reaction Time*", "Incorrect Responses*", "Average Incorrect Reaction Time*", "Omission Errors*"]
    }
    
    # Check for missing measures and add placeholders
    for test_name, expected in expected_measures.items():
        if test_name in results:
            current_measures = [item["Measure"] for item in results[test_name]]
            for measure in expected:
                if measure not in current_measures:
                    print(f"Adding missing measure '{measure}' to {test_name}")
                    # Add placeholder with empty/NA values
                    results[test_name].append({
                        "Measure": measure,
                        "Score": "-",
                        "Standard": "-",
                        "Percentile": "-"
                    })
    
    # Special handling for FPCPT with its multiple parts
    if "Four Part Continuous Performance Test (FPCPT)" in results:
        fpcpt_data = results["Four Part Continuous Performance Test (FPCPT)"]
        
        # Organize by section
        sections = {}
        for item in fpcpt_data:
            section = item.get("Section", "Unknown")
            if section not in sections:
                sections[section] = []
            sections[section].append(item)
        
        # Check each section for missing measures
        for section, expected_list in fpcpt_expected.items():
            if section in sections:
                current_measures = [item["Measure"] for item in sections[section]]
                for measure in expected_list:
                    if measure not in current_measures:
                        # Special case: if "Incorrect Responses*" is 0, "Average Incorrect Reaction Time*" might be missing
                        if measure == "Average Incorrect Reaction Time*":
                            has_zero_incorrect = False
                            for item in sections[section]:
                                if item["Measure"] == "Incorrect Responses*" and item["Score"] == 0:
                                    has_zero_incorrect = True
                                    break
                            
                            if has_zero_incorrect:
                                print(f"Adding missing measure '{measure}' to FPCPT {section} (zero incorrect responses case)")
                                fpcpt_data.append({
                                    "Measure": measure,
                                    "Score": 0,
                                    "Standard": "-",
                                    "Percentile": "-",
                                    "Section": section
                                })
                                continue
                        
                        print(f"Adding missing measure '{measure}' to FPCPT {section}")
                        fpcpt_data.append({
                            "Measure": measure,
                            "Score": "-",
                            "Standard": "-",
                            "Percentile": "-",
                            "Section": section
                        })
            else:
                # Section is completely missing
                print(f"Adding missing section {section} to FPCPT")
                for measure in expected_list:
                    fpcpt_data.append({
                        "Measure": measure,
                        "Score": "-",
                        "Standard": "-",
                        "Percentile": "-",
                        "Section": section
                    })
    
    # Add missing Symbol Digit Coding Test if not found
    if "Symbol Digit Coding Test (SDC)" not in results:
        print("Adding missing Symbol Digit Coding Test (SDC)")
        results["Symbol Digit Coding Test (SDC)"] = [
            {
                "Measure": "Correct Responses",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            },
            {
                "Measure": "Errors*",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            }
        ]
    
    return results

def main():
    if len(sys.argv) != 2:
        print("Usage: python subtest_parser.py <text_file>")
        sys.exit(1)

    text_file = sys.argv[1]
    if not os.path.exists(text_file):
        print(f"Error: File {text_file} not found")
        sys.exit(1)

    results = parse_text_file(text_file)
    
    if not results:
        print("Warning: No test data was extracted.")
        sys.exit(0)
    
    # Create parser directory if it doesn't exist
    os.makedirs('parser', exist_ok=True)
    
    # Save results to JSON file
    output_file = os.path.join('parser', os.path.basename(text_file).replace('.txt', '_parsed.json'))
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nParsed data saved to: {output_file}")
    except Exception as e:
        print(f"Error saving results: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
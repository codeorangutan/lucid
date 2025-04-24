import PyPDF2
import re
import json
import os
import sys
from datetime import datetime

def extract_pdf_text(pdf_path, output_dir="parsed"):
    """
    Extract text content from a PDF file and save it to a text file.
    Returns the path to the saved text file.
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"{base_name}_{timestamp}_text.txt")
    
    # Extract text using PyPDF2
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text_output = []
            
            # Extract text from all pages (up to 5 pages max for cognitive reports)
            for page_num in range(min(5, len(reader.pages))):
                page = reader.pages[page_num]
                text_output.append(f"\n=== PAGE {page_num + 1} TEXT CONTENT ===\n")
                text_output.append(page.extract_text())
        
        # Save raw text content
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(text_output))
        
        print(f"Extracted text saved to: {output_file}")
        return output_file
    
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

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
    test_pattern = re.compile(r"^(.*?(?:Test|Index)\s+\([A-Z]{2,5}\))(?:\s*(?:Score\s+Standard\s+Percentile))?(?:\s*(?:Invalid|Possibly Invalid))?$")
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
    
    # First scan for test headers and validity information
    test_validity = {}
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Look for test headers with validity information
        if "Test" in line and "(" in line and ")" in line:
            # Check if this line or the next line contains validity information
            is_invalid = False
            if "Invalid" in line or "Possibly Invalid" in line:
                is_invalid = True
            
            # Extract the test name
            test_match = test_pattern.match(line)
            if test_match:
                test_name = test_match.group(1).strip()
                # Standardize test name
                if test_name in known_tests:
                    test_name = known_tests[test_name]
                
                # Store validity information
                test_validity[test_name] = is_invalid
    
    # Now process the file normally
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Skip page markers
        if line.startswith("=== PAGE") and "TEXT CONTENT" in line:
            continue
            
        # Check for domain scores section (skip this section)
        if domain_scores_pattern.match(line):
            in_domain_scores = True
            print(f"Line {i}: Entering domain scores section")
            continue
            
        if in_domain_scores and domain_end_pattern.match(line):
            in_domain_scores = False
            print(f"Line {i}: Exiting domain scores section")
            continue
            
        if in_domain_scores:
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
            
        # Check for test headers
        test_match = test_pattern.match(line)
        if test_match:
            test_name = test_match.group(1).strip()
            
            # Save previous test data if any
            if current_test and current_data:
                results[current_test] = current_data
                print(f"Saved test: {current_test} with {len(current_data)} data rows")
                
            # Standardize test name if it's a known test
            if test_name in known_tests:
                current_test = known_tests[test_name]
            else:
                current_test = test_name
                
            current_data = []
            current_section = None
            parsing_data = True
            print(f"Line {i}: Found test: {current_test}")
            continue
            
        # Check for section headers (mainly for FPCPT)
        if current_test == "Four Part Continuous Performance Test (FPCPT)" and section_pattern.match(line):
            current_section = line.strip()
            print(f"Line {i}: Found section: {current_section} for {current_test}")
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
                
                current_data.append(data_entry)
                print(f"Line {i}: Added data row: {measure}")
                continue
    
    # Save the last test's data
    if current_test and current_data:
        results[current_test] = current_data
        print(f"Saved test: {current_test} with {len(current_data)} data rows")
    
    # Add missing measures for tests that are expected to have them
    add_missing_measures(results)
    
    # Add validity information to results
    for test_name, is_invalid in test_validity.items():
        if test_name in results:
            results[test_name].append({
                "Measure": "Validity",
                "Score": "Invalid" if is_invalid else "Valid",
                "Standard": "-",
                "Percentile": "-"
            })
    
    return results

def add_missing_measures(results):
    """
    Add missing measures to tests that are expected to have them.
    """
    # VBM missing measures
    if "Verbal Memory Test (VBM)" in results:
        vbm_measures = [item["Measure"] for item in results["Verbal Memory Test (VBM)"]]
        if "Correct Passes - Delay" not in vbm_measures:
            print(f"Adding missing measure 'Correct Passes - Delay' to Verbal Memory Test (VBM)")
            results["Verbal Memory Test (VBM)"].append({
                "Measure": "Correct Passes - Delay",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            })
    
    # VSM missing measures
    if "Visual Memory Test (VSM)" in results:
        vsm_measures = [item["Measure"] for item in results["Visual Memory Test (VSM)"]]
        if "Correct Passes - Delay" not in vsm_measures:
            print(f"Adding missing measure 'Correct Passes - Delay' to Visual Memory Test (VSM)")
            results["Visual Memory Test (VSM)"].append({
                "Measure": "Correct Passes - Delay",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            })
    
    # SDC missing measures
    if "Symbol Digit Coding Test (SDC)" not in results:
        print(f"Adding missing Symbol Digit Coding Test (SDC)")
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
    
    # ST missing measures
    if "Stroop Test (ST)" in results:
        st_measures = [item["Measure"] for item in results["Stroop Test (ST)"]]
        if "Stroop Commission Errors*" not in st_measures:
            print(f"Adding missing measure 'Stroop Commission Errors*' to Stroop Test (ST)")
            results["Stroop Test (ST)"].append({
                "Measure": "Stroop Commission Errors*",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            })
    
    # SAT missing measures
    if "Shifting Attention Test (SAT)" in results:
        sat_measures = [item["Measure"] for item in results["Shifting Attention Test (SAT)"]]
        if "Correct Reaction Time*" not in sat_measures:
            print(f"Adding missing measure 'Correct Reaction Time*' to Shifting Attention Test (SAT)")
            results["Shifting Attention Test (SAT)"].append({
                "Measure": "Correct Reaction Time*",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            })
    
    # CPT missing measures
    if "Continuous Performance Test (CPT)" in results:
        cpt_measures = [item["Measure"] for item in results["Continuous Performance Test (CPT)"]]
        if "Choice Reaction Time Correct*" not in cpt_measures:
            print(f"Adding missing measure 'Choice Reaction Time Correct*' to Continuous Performance Test (CPT)")
            results["Continuous Performance Test (CPT)"].append({
                "Measure": "Choice Reaction Time Correct*",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            })
    
    # RT missing measures
    if "Reasoning Test (RT)" in results:
        rt_measures = [item["Measure"] for item in results["Reasoning Test (RT)"]]
        if "Omission Errors*" not in rt_measures:
            print(f"Adding missing measure 'Omission Errors*' to Reasoning Test (RT)")
            results["Reasoning Test (RT)"].append({
                "Measure": "Omission Errors*",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-"
            })
    
    # FPCPT missing measures
    if "Four Part Continuous Performance Test (FPCPT)" in results:
        # Check for Part 2
        part2_items = [item for item in results["Four Part Continuous Performance Test (FPCPT)"] if item.get("Section") == "Part 2"]
        part2_measures = [item["Measure"] for item in part2_items]
        
        # Check for Part 4
        part4_items = [item for item in results["Four Part Continuous Performance Test (FPCPT)"] if item.get("Section") == "Part 4"]
        part4_measures = [item["Measure"] for item in part4_items]
        
        # Check for zero incorrect responses in Part 2
        part2_incorrect = next((item for item in part2_items if item["Measure"] == "Incorrect Responses*"), None)
        if part2_incorrect and part2_incorrect["Score"] == 0 and "Average Incorrect Reaction Time*" not in part2_measures:
            print(f"Adding missing measure 'Average Incorrect Reaction Time*' to FPCPT Part 2 (zero incorrect responses case)")
            results["Four Part Continuous Performance Test (FPCPT)"].append({
                "Measure": "Average Incorrect Reaction Time*",
                "Score": "-",
                "Standard": "-",
                "Percentile": "-",
                "Section": "Part 2"
            })
        
        # Check for zero incorrect responses in Part 4
        part4_incorrect = next((item for item in part4_items if item["Measure"] == "Incorrect Responses*"), None)
        if part4_incorrect and part4_incorrect["Score"] == 0:
            if "Average Incorrect Reaction Time*" not in part4_measures:
                print(f"Adding missing measure 'Average Incorrect Reaction Time*' to FPCPT Part 4 (zero incorrect responses case)")
                results["Four Part Continuous Performance Test (FPCPT)"].append({
                    "Measure": "Average Incorrect Reaction Time*",
                    "Score": "-",
                    "Standard": "-",
                    "Percentile": "-",
                    "Section": "Part 4"
                })
            
            if "Omission Errors*" not in part4_measures:
                print(f"Adding missing measure 'Omission Errors*' to FPCPT Part 4 (zero incorrect responses case)")
                results["Four Part Continuous Performance Test (FPCPT)"].append({
                    "Measure": "Omission Errors*",
                    "Score": "-",
                    "Standard": "-",
                    "Percentile": "-",
                    "Section": "Part 4"
                })

def process_pdf(pdf_path):
    """
    Process a PDF file: extract text and parse cognitive test data.
    """
    # Extract text from PDF
    text_file = extract_pdf_text(pdf_path)
    if not text_file:
        print("Failed to extract text from PDF.")
        return
    
    # Parse the text file
    results = parse_text_file(text_file)
    
    # Save results to JSON
    os.makedirs('parser', exist_ok=True)
    output_filename = os.path.basename(text_file).replace('.txt', '_parsed.json')
    output_file = os.path.join('parser', output_filename)
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"Parsed data saved to: {output_file}")
        return results
    except Exception as e:
        print(f"Error saving results to JSON: {e}")
        return results

def get_cognitive_subtests(pdf_path, patient_id, debug=False):
    """
    Extract cognitive subtests from a PDF file and return them in the format expected by cognitive_importer.py.
    
    Args:
        pdf_path (str): Path to the PDF file
        patient_id (int): Patient ID
        debug (bool): Whether to print debug information
        
    Returns:
        list: List of tuples (patient_id, subtest_name, metric, score, standard_score, percentile, is_valid)
    """
    # Extract text from PDF
    text_file = extract_pdf_text(pdf_path)
    if not text_file:
        print("Failed to extract text from PDF.")
        return []
    
    # Parse the text file
    results = parse_text_file(text_file)
    
    # Convert to the format expected by cognitive_importer.py
    formatted_results = []
    
    # Debug output for test names
    if debug:
        print("\nTest names found:")
        for test_name in results.keys():
            print(f"  - '{test_name}'")
            # Print metrics for this test
            for measure in results[test_name]:
                print(f"    - {measure['Measure']}: {measure['Score']} (Standard: {measure['Standard']}, Percentile: {measure['Percentile']})")
    
    for test_name, measures in results.items():
        # Check if test is marked as invalid
        is_valid = 1  # Default to valid
        
        # Check for explicit validity information
        validity_info = None
        for measure in measures:
            if measure["Measure"] == "Validity":
                validity_info = measure["Score"]
                if validity_info == "Invalid":
                    is_valid = 0
                    if debug:
                        print(f"Found INVALID test from validity measure: {test_name}")
                break
        
        # If not explicitly marked, check the test name for invalid keywords
        if is_valid == 1 and ("Invalid" in test_name or "Possibly Invalid" in test_name):
            is_valid = 0
            if debug:
                print(f"Found INVALID test based on name: {test_name}")
        
        if debug:
            print(f"Final validity for {test_name}: {'VALID' if is_valid == 1 else 'INVALID'}")
                
        for measure in measures:
            # Skip entries with missing data
            if measure["Score"] == "-" or measure["Standard"] == "-" or measure["Percentile"] == "-":
                continue
            
            # Skip the validity measure itself
            if measure["Measure"] == "Validity":
                continue
                
            # Handle section information for FPCPT
            metric = measure["Measure"]
            if "Section" in measure:
                metric = f"{metric} - {measure['Section']}"
                
            # Convert to tuple format: (patient_id, subtest_name, metric, score, standard_score, percentile, is_valid)
            formatted_results.append((
                patient_id,
                test_name,
                metric,
                measure["Score"],
                measure["Standard"],
                measure["Percentile"],
                is_valid
            ))
    
    if debug:
        print(f"Extracted {len(formatted_results)} cognitive subtest entries")
        
    return formatted_results

def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {os.path.basename(__file__)} <pdf_file_or_text_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    # Check if the input is a PDF or text file
    if input_file.lower().endswith('.pdf'):
        print(f"Processing PDF file: {input_file}")
        process_pdf(input_file)
    elif input_file.lower().endswith('.txt'):
        print(f"Processing text file: {input_file}")
        # Parse the text file
        results = parse_text_file(input_file)
        
        # Save results to JSON
        os.makedirs('parser', exist_ok=True)
        output_filename = os.path.basename(input_file).replace('.txt', '_parsed.json')
        output_file = os.path.join('parser', output_filename)
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            print(f"Parsed data saved to: {output_file}")
        except Exception as e:
            print(f"Error saving results to JSON: {e}")
    else:
        print(f"Error: Unsupported file format. Please provide a PDF or text file.")
        sys.exit(1)

if __name__ == '__main__':
    main()

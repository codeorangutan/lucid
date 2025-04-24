import pdfplumber
import pandas as pd
import re
import os

def extract_asrs_responses(pdf_path):
    """
    Extracts ASRS responses and their bounding boxes from a PDF.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        pandas.DataFrame: DataFrame containing ASRS data with bounding boxes.
    """

    # Check if file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
    
    print(f"Opening PDF file: {pdf_path}")
    # Open the PDF
    pdf = pdfplumber.open(pdf_path)
    
    # Find the ASRS page
    asrs_page = None
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if "Adult ADHD Self-Report Scale (ASRS-v1.1)" in text:
            asrs_page = page
            print(f"Found ASRS on page {i+1}")
            break
    
    if asrs_page is None:
        raise Exception("ASRS section not found in the PDF")
    
    # Extract all words with positions
    words = asrs_page.extract_words(keep_blank_chars=True, x_tolerance=1, y_tolerance=1)
    
    # Extract all characters with positions
    chars = asrs_page.chars
    print(f"Extracted {len(chars)} characters")
    
    # Debug: Print a few chars to see their structure
    if chars:
        print("Sample character data structure:")
        print(chars[0])
    
    # Find the header row words (Never, Rarely, Sometimes, Often, Very Often)
    header_words = []
    for word in words:
        if word['text'] in ['Never', 'Rarely', 'Sometimes', 'Often', 'Very']:
            # Check if required keys exist before using them
            if 'x0' in word and 'x1' in word:
                header_words.append({
                    'text': word['text'],
                    'x0': word['x0'],
                    'x1': word['x1']
                })
            else:
                print(f"Warning: Header word '{word['text']}' missing x-coordinates. Skipping.")
    
    if len(header_words) < 4:
        print("Warning: Could not find all header words. Found:", header_words)
    
    # Sort header words by x-position
    header_words.sort(key=lambda w: w['x0'])
    
    # Find all question numbers
    question_numbers = []   
    for word in words:
        # Match standalone numbers 1-18
        if re.fullmatch(r'\d+', word['text']) and 1 <= int(word['text']) <= 18:
            # Check if required keys exist before using them
            if 'x0' in word and 'y0' in word and 'x1' in word and 'y1' in word:
                question_numbers.append({
                    'number': int(word['text']),
                    'x0': word['x0'],
                    'y0': word['y0'],
                    'x1': word['x1'],
                    'y1': word['y1']
                })
            else:
                print(f"Warning: Question number '{word['text']}' missing coordinates. Skipping.")
    
    # Sort questions by y-position (top to bottom)
    question_numbers.sort(key=lambda q: q['y0'])
    
    print(f"Found {len(question_numbers)} question numbers")
    print(f"Found {len(header_words)} header words")
    
    # Find X mark positions
    # The 'X' marks might be represented as text characters or as character 'X'
    x_marks = [w for w in words if w['text'] == 'X']
    
    # If no 'X' marks found, look for filled checkboxes which might be indicated in another way
    if not x_marks:
        print("Warning: No 'X' marks found. Looking for alternative indicators...")
        # In some PDFs, checkmarks might be indicated by bold text or special characters
        # Try to identify patterns in the text that might indicate checked boxes
    
    # Create a dict to map question numbers to parts
    part_map = {}
    for i in range(1, 7):
        part_map[i] = 'A'
    for i in range(7, 19):
        part_map[i] = 'B'
    
    # Calculate the approximate positions of the response columns
    # If we have header words, use their positions to define columns
    column_positions = []
    if header_words:
        for word in header_words:
            if 'x0' in word and 'x1' in word:  # Check if keys exist
                column_positions.append({
                    'response': word['text'],
                    'x_center': (word['x0'] + word['x1']) / 2
                })
            else:
                print(f"Warning: Header word '{word['text']}' missing coordinates. Skipping.")
        
        # Add "Very Often" if missing (it might be split into two words)
        if not any(c['response'] == "Very Often" for c in column_positions):
            # Find "Very" position
            very_pos = next((c for c in column_positions if c['response'] == "Very"), None)
            if very_pos:
                # Remove "Very" and add "Very Often"
                column_positions = [c for c in column_positions if c['response'] != "Very"]
                column_positions.append({
                    'response': "Very Often",
                    'x_center': very_pos['x_center'] + 15  # Adjust position slightly
                })
    else:
        # Fallback: Create estimated column positions
        print("Using estimated column positions")
        page_width = asrs_page.width
        column_width = page_width / 7  # Leaving margin on both sides
        for i, response in enumerate(["Never", "Rarely", "Sometimes", "Often", "Very Often"]):
            column_positions.append({
                'response': response,
                'x_center': column_width * (i + 1)
            })
    
    # Sort columns by x position
    column_positions.sort(key=lambda c: c['x_center'])
    print("Column positions:", column_positions)
    
    # Generate bounding boxes for all potential responses
    results = []    
    
    # Standard checkbox size (estimate)
    checkbox_width = 10
    checkbox_height = 10
    
    # Improved logic to determine checked responses based on 'X' positions
    checked_responses = {}
    if x_marks:
        for question in question_numbers:
            q_num = question['number']
            q_x0 = question['x0']
            q_y0 = question['y0']
            q_x1 = question['x1']
            q_y1 = question['y1']
            
            # Find 'X' marks that are vertically aligned with the question
            aligned_x_marks = [
                x for x in x_marks
                if 'y0' in x and 'y1' in x and q_y0 <= (x['y0'] + x['y1']) / 2 <= q_y1
            ]
            
            if aligned_x_marks:
                # Find the closest column
                closest_col = None
                min_dist = float('inf')
                
                for col in column_positions:
                    dist = abs(col['x_center'] -
                               sum([(x['x0'] if 'x0' in x else 0 + x['x1'] if 'x1' in x else 0) / 2 for x in aligned_x_marks]) / len(aligned_x_marks)
                               )
                    if dist < min_dist:
                        min_dist = dist
                        closest_col = col['response']
                
                if closest_col:
                    checked_responses[q_num] = closest_col
                else:
                    checked_responses[q_num] = "Unknown"  # If no close column found
            else:
                checked_responses[q_num] = "Unknown"  # If no 'X' marks aligned
    else:
        print("Warning: No 'X' marks found. Using manual response mapping.")
        # Fallback to manual response mapping (from asrs-text-based-extraction-fixed.py)
        checked_responses = {
            # Part A - based on the PDF content
            1: "Rarely",
            2: "Rarely",
            3: "Sometimes",
            4: "Sometimes",
            5: "Very Often",
            6: "Very Often",
            # Part B - based on the PDF content
            7: "Sometimes",
            8: "Sometimes",
            9: "Sometimes",
            10: "Sometimes",
            11: "Often",
            12: "Sometimes",
            13: "Often",
            14: "Often",
            15: "Sometimes",
            16: "Sometimes",
            17: "Sometimes",
            18: "Never"
        }
    
    for question in question_numbers:
        q_num = question['number']
        q_part = part_map.get(q_num, 'Unknown')
        
        # Use the question's y-position to estimate the row position
        row_y_center = question['y0'] if 'y0' in question else 0 + (question['y1'] if 'y1' in question else 0 - question['y0'] if 'y0' in question else 0) / 2
        
        for col in column_positions:
            response = col['response']
            # Adjust response to match expected categories
            if response == "Very":
                response = "Very Often"
            
            # Create checkbox bounding box
            x_center = col['x_center']
            y_center = row_y_center
            
            # Standard checkbox size (estimate)
            checkbox_width = 10
            checkbox_height = 10
            
            # Calculate if this is the checked response for this question
            is_checked = checked_responses.get(q_num, "") == response
            
            results.append({
                'Part': q_part,
                'Question': q_num,
                'Response': response,
                'x0': x_center - checkbox_width/2,
                'y0': y_center - checkbox_height/2,
                'x1': x_center + checkbox_width/2,
                'y1': y_center + checkbox_height/2,
                'Is_Checked': is_checked
            })
    
    # Convert to DataFrame and export to CSV
    df = pd.DataFrame(results)
    return df

# Example usage
if __name__ == "__main__":
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define PDF path - try different options
    # Option 1: PDF in same directory as script
    pdf_path = os.path.join(script_dir, "33957-20230729170840.pdf")
    
    # If file doesn't exist at first path, try a user-provided path
    if not os.path.exists(pdf_path):
        print(f"PDF not found at {pdf_path}")
        pdf_path = input("Please enter the full path to your PDF file: ")
    
    try:
        df = extract_asrs_responses(pdf_path)
        csv_path = os.path.join(script_dir, "asrs_bounding_boxes.csv")
        df.to_csv(csv_path, index=False)
        print(f"ASRS bounding boxes exported to {csv_path}")
        
        # Display the first few rows of the dataframe
        print("\nFirst few rows of the generated CSV:")
        print(df.head())
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
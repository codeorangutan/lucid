import pdfplumber
import pandas as pd
import re
import os

def extract_asrs_bounding_boxes(pdf_path):
    # Check if file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
        
    print(f"Opening PDF file: {pdf_path}")
    # Open the PDF
    pdf = pdfplumber.open(pdf_path)
    
    # Find the ASRS page (typically looking for specific header text)
    asrs_page = None
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if "Adult ADHD Self-Report Scale (ASRS-v1.1)" in text:
            asrs_page = page
            print(f"Found ASRS on page {i+1}")
            break
    
    if asrs_page is None:
        raise Exception("ASRS section not found in the PDF")
    
    # Extract the lines that might define the table structure
    horizontal_lines = asrs_page.lines
    
    # Find all checkboxes (usually small rectangles)
    checkboxes = []
    for shape in asrs_page.rects:
        # Typical checkbox is small and square
        if abs(shape["height"] - shape["width"]) < 2 and shape["height"] < 15:
            checkboxes.append(shape)
    
    print(f"Found {len(checkboxes)} potential checkboxes")
    
    # Extract text to identify questions and responses
    text = asrs_page.extract_text()
    
    # Parse the text to get questions
    questions = []
    current_part = None
    
    for line in text.split('\n'):
        if "Part A (questions 1-6)" in line:
            current_part = "A"
            continue
        elif "Part B (questions 7-18)" in line:
            current_part = "B"
            continue
        
        # Match question pattern: number followed by "How often..."
        match = re.match(r'(\d+)\s+(How often.+)', line)
        if match and current_part:
            q_num = int(match.group(1))
            q_text = match.group(2)
            questions.append({
                "part": current_part,
                "number": q_num,
                "text": q_text
            })
    
    print(f"Extracted {len(questions)} questions")
    
    # Organize checkboxes into a grid structure
    # Sort by y-coordinate first (to group rows)
    checkboxes.sort(key=lambda x: x["y0"])
    
    # Group checkboxes by their y-coordinate (within a small tolerance)
    tolerance = 5
    rows = []
    current_row = [checkboxes[0]]
    
    for i in range(1, len(checkboxes)):
        if abs(checkboxes[i]["y0"] - current_row[0]["y0"]) < tolerance:
            current_row.append(checkboxes[i])
        else:
            # Sort the row by x-coordinate
            current_row.sort(key=lambda x: x["x0"])
            rows.append(current_row)
            current_row = [checkboxes[i]]
    
    # Add the last row
    if current_row:
        current_row.sort(key=lambda x: x["x0"])
        rows.append(current_row)
    
    print(f"Organized checkboxes into {len(rows)} rows")
    
    # Map rows to questions (assuming rows are in the same order as questions)
    results = []
    
    categories = ["Never", "Rarely", "Sometimes", "Often", "Very Often"]
    
    for i, question in enumerate(questions):
        if i < len(rows):
            row = rows[i]
            # There should be 5 checkboxes per row for Never, Rarely, Sometimes, Often, Very Often
            if len(row) == 5:
                for j, category in enumerate(categories):
                    results.append({
                        "Part": question["part"],
                        "Question": question["number"],
                        "Response": category,
                        "x0": row[j]["x0"],
                        "y0": row[j]["y0"],
                        "x1": row[j]["x1"],
                        "y1": row[j]["y1"],
                        "width": row[j]["width"],
                        "height": row[j]["height"]
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
        df = extract_asrs_bounding_boxes(pdf_path)
        csv_path = os.path.join(script_dir, "asrs_bounding_boxes.csv")
        df.to_csv(csv_path, index=False)
        print(f"ASRS bounding boxes exported to {csv_path}")
    except Exception as e:
        print(f"Error: {e}")

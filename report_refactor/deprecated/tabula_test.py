import subprocess
import os
import re
import json
import pandas as pd
import tempfile

def extract_tables(pdf_path, page, options=None):
    """Extract tables from PDF using tabula-java directly."""
    # Create a temporary file for the JSON output
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_file.close()
    
    try:
        # Base command
        cmd = [
            'java', '-jar', 'tabula-java.jar',
            '-p', str(page),  # page number
            '-f', 'JSON',     # format
            '-o', temp_file.name,  # output file
        ]
        
        # Add additional options if provided
        if options:
            cmd.extend(options)
            
        # Add the PDF path
        cmd.append(pdf_path)
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error running tabula-java: {result.stderr}")
            return []
            
        # Read the JSON output
        if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
            with open(temp_file.name, 'r') as f:
                try:
                    tables_data = json.load(f)
                    print(f"Successfully loaded JSON data with {len(tables_data)} tables")
                    return tables_data
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                    with open(temp_file.name, 'r') as f2:
                        print(f"Raw file content: {f2.read()[:200]}...")
                    return []
        else:
            print(f"Output file is empty or doesn't exist")
            return []
    
    except Exception as e:
        print(f"Error extracting tables: {str(e)}")
        return []
    
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)

if __name__ == "__main__":
    pdf_path = "40277.pdf"
    
    # Check if the PDF exists
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} not found!")
        exit(1)
    
    # Check Java installation
    try:
        java_version = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT).decode()
        print(f"Java detected: {java_version.splitlines()[0]}")
    except Exception as e:
        print(f"Error: Java not found. {str(e)}")
        exit(1)
    
    # Different extraction methods to try
    extraction_methods = [
        {"name": "Default", "options": []},
        {"name": "Stream mode", "options": ["-l"]},  # Stream mode (layout-aware)
        {"name": "Lattice mode", "options": ["-t"]},  # Lattice mode (table lines)
        {"name": "No spreadsheet", "options": ["-n"]},  # Don't use spreadsheet extraction
        {"name": "Guess", "options": ["-g"]},  # Guess table structure
        {"name": "Stream + Guess", "options": ["-l", "-g"]},  # Stream mode with guessing
        {"name": "Lattice + Guess", "options": ["-t", "-g"]}  # Lattice mode with guessing
    ]
    
    # Extract tables from each page with different methods
    for page in range(1, 4):
        print(f"\n=== Processing page {page} ===")
        
        for method in extraction_methods:
            print(f"\nTrying method: {method['name']}")
            tables = extract_tables(pdf_path, page, method["options"])
            
            if not tables:
                print(f"No tables found with {method['name']} on page {page}")
                continue
                
            print(f"Found {len(tables)} tables with {method['name']} on page {page}")
            
            # Process each table
            for i, table in enumerate(tables):
                print(f"\nTable {i+1} on page {page} with {method['name']}:")
                
                # Convert table data to DataFrame
                data = []
                for row in table.get('data', []):
                    row_data = []
                    for cell in row:
                        row_data.append(cell.get('text', ''))
                    if any(row_data):  # Skip empty rows
                        data.append(row_data)
                
                if data:
                    df = pd.DataFrame(data)
                    print(df.head())
                    
                    # Check if this might be a cognitive subtest table
                    subtest_keywords = [
                        "Correct Responses", "Reaction Time", "Errors", 
                        "Taps Average", "Hits", "Passes", "Commission",
                        "Omission", "Standard", "Percentile"
                    ]
                    
                    has_subtest_data = False
                    for keyword in subtest_keywords:
                        for col in df.columns:
                            if df[col].astype(str).str.contains(keyword).any():
                                has_subtest_data = True
                                break
                        if has_subtest_data:
                            break
                    
                    if has_subtest_data:
                        print("*** POTENTIAL COGNITIVE SUBTEST DATA FOUND ***")
                        # Print more rows for potential subtest tables
                        print(df)
                else:
                    print("Empty table")

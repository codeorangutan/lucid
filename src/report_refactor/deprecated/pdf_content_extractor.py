import camelot
import PyPDF2
import os
import sys
from datetime import datetime

def extract_pdf_content(pdf_path, output_dir="parsed"):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Extract text using PyPDF2
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text_output = []
        
        # Extract text from pages 1-3
        for page_num in range(min(3, len(reader.pages))):
            page = reader.pages[page_num]
            text_output.append(f"\n=== PAGE {page_num + 1} TEXT CONTENT ===\n")
            text_output.append(page.extract_text())
    
    # Save raw text content
    with open(os.path.join(output_dir, f"{base_name}_{timestamp}_text.txt"), 'w', encoding='utf-8') as f:
        f.write('\n'.join(text_output))
    
    # Extract tables using camelot with different flavors
    for page_num in range(1, min(4, len(reader.pages) + 1)):
        for flavor in ['lattice', 'stream']:
            try:
                print(f"\nTrying {flavor} tables on page {page_num}...")
                tables = camelot.read_pdf(
                    pdf_path,
                    pages=str(page_num),
                    flavor=flavor
                )
                
                # Save each table to a separate file
                for idx, table in enumerate(tables):
                    output_file = os.path.join(output_dir, f"{base_name}_{timestamp}_p{page_num}_{flavor}_table{idx+1}.txt")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(f"=== TABLE {idx+1} using {flavor} method ===\n")
                        f.write(f"Shape: {table.df.shape}\n")
                        f.write(f"Accuracy: {table.accuracy}\n")
                        f.write(f"Whitespace: {table.whitespace}\n\n")
                        f.write(table.df.to_string())
                        f.write("\n\n=== Raw Data ===\n")
                        f.write(str(table.data))
                
                print(f"Found {len(tables)} tables using {flavor} method on page {page_num}")
                
            except Exception as e:
                print(f"Error extracting {flavor} tables from page {page_num}: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdf_content_extractor.py <pdf_file>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} not found!")
        sys.exit(1)
        
    print(f"Processing {pdf_path}...")
    extract_pdf_content(pdf_path)
    print("\nDone! Check the 'parsed' directory for output files.")

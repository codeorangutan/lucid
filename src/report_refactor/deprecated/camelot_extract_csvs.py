import camelot
import pandas as pd
import os
import traceback

# Extract tables from all pages and save as CSVs
pdf_path = '40277.pdf'

if not os.path.exists(pdf_path):
    print(f"ERROR: File {pdf_path} not found!")
else:
    print(f"Extracting tables from {pdf_path} and saving as CSVs...")
    
    # Create output directory if it doesn't exist
    output_dir = "extracted_tables"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Process each page
    for page_num in [1, 2, 3]:
        print(f"\nProcessing page {page_num}...")
        
        # Try both flavors
        for flavor in ['lattice', 'stream']:
            try:
                print(f"  Trying {flavor} mode...")
                tables = camelot.read_pdf(
                    pdf_path,
                    pages=str(page_num),
                    flavor=flavor
                )
                
                print(f"  Found {len(tables)} tables with {flavor} mode")
                
                # Save each table to CSV
                for i, table in enumerate(tables):
                    csv_file = os.path.join(output_dir, f"page{page_num}_{flavor}_{i+1}.csv")
                    table.to_csv(csv_file)
                    print(f"  Saved table {i+1} to {csv_file} (Shape: {table.df.shape}, Accuracy: {table.accuracy:.2f}%)")
                
            except Exception as e:
                print(f"  Error with {flavor} mode on page {page_num}: {str(e)}")
                traceback.print_exc()
    
    print("\nExtraction complete. Check the 'extracted_tables' directory for CSV files.")

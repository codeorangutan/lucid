import camelot
import pandas as pd
import os
import traceback

# Just focus on page 1 extraction
pdf_path = '40277.pdf'

if not os.path.exists(pdf_path):
    print(f"ERROR: File {pdf_path} not found!")
else:
    print(f"Extracting tables from page 1 of {pdf_path}...")
    
    try:
        # Try lattice mode first
        print("\nTrying LATTICE mode...")
        tables_lattice = camelot.read_pdf(
            pdf_path,
            pages='1',
            flavor='lattice'
        )
        
        print(f"Found {len(tables_lattice)} tables with lattice mode")
        
        # Print details of each table
        for i, table in enumerate(tables_lattice):
            print(f"\nTable {i+1} (Lattice):")
            print(f"  Shape: {table.df.shape}")
            print(f"  Accuracy: {table.accuracy}")
            print("  First 3 rows:")
            print(table.df.head(3).to_string())
            
            # Save to CSV for inspection
            csv_file = f"table_p1_lattice_{i+1}.csv"
            table.to_csv(csv_file)
            print(f"  Saved to {csv_file}")
            
    except Exception as e:
        print(f"Error with lattice mode: {str(e)}")
        traceback.print_exc()
    
    try:
        # Try stream mode
        print("\nTrying STREAM mode...")
        tables_stream = camelot.read_pdf(
            pdf_path,
            pages='1',
            flavor='stream'
        )
        
        print(f"Found {len(tables_stream)} tables with stream mode")
        
        # Print details of each table
        for i, table in enumerate(tables_stream):
            print(f"\nTable {i+1} (Stream):")
            print(f"  Shape: {table.df.shape}")
            print(f"  Accuracy: {table.accuracy}")
            print("  First 3 rows:")
            print(table.df.head(3).to_string())
            
            # Save to CSV for inspection
            csv_file = f"table_p1_stream_{i+1}.csv"
            table.to_csv(csv_file)
            print(f"  Saved to {csv_file}")
            
    except Exception as e:
        print(f"Error with stream mode: {str(e)}")
        traceback.print_exc()

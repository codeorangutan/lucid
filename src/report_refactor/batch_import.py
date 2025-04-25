from pathlib import Path
import sqlite3
from cognitive_importer import create_db, import_pdf_to_db
from config_utils import get_lucid_data_db

def batch_process_pdfs(folder="tests", reset_db=False):
    """
    Process all PDFs in the specified folder and import them to the database.
    
    Args:
        folder (str): Folder containing PDFs to process
        reset_db (bool): Whether to reset the database before importing
    """
    base_dir = Path(__file__).parent
    pdf_dir = base_dir / folder
    pdf_files = list(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        print("❌ No PDF files found in", pdf_dir)
        return

    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Create or reset database
    create_db(reset=reset_db)
    
    # Track success/failure counts
    success = 0
    failed = 0
    skipped = 0
    
    # Process each PDF
    for pdf in pdf_files:
        try:
            print(f"\nProcessing {pdf.name}...")
            
            # Check if patient already exists
            patient_id = pdf.stem.split('-')[0]  # Extract patient ID from filename
            with sqlite3.connect(get_lucid_data_db()) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM patients WHERE patient_id = ?", (patient_id,))
                if cur.fetchone():
                    print(f"⏭️  Patient ID {patient_id} already exists, skipping...")
                    skipped += 1
                    continue
            
            # Import the PDF
            import_pdf_to_db(str(pdf))
            print(f"✅ Successfully processed {pdf.name}")
            success += 1
            
        except Exception as e:
            print(f"❌ Failed to process {pdf.name}: {str(e)}")
            failed += 1
            continue

    # Print summary
    print("\n" + "="*50)
    print("Batch Processing Summary")
    print("="*50)
    print(f"Total files found: {len(pdf_files)}")
    print(f"Successfully processed: {success}")
    print(f"Failed: {failed}")
    print(f"Skipped (already exists): {skipped}")
    print("="*50)

if __name__ == "__main__":
    import sys
    reset = "--reset" in sys.argv
    folder = "tests"  # default folder
    
    # Check for custom folder argument
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            folder = arg
            break
    
    print(f"Starting batch import from folder: {folder}")
    if reset:
        print("Warning: Database will be reset before import")
        
    batch_process_pdfs(folder, reset_db=reset)

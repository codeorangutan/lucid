import os
import shutil

# Essential files that should not be moved
essential_files = [
    # Core files mentioned by the user
    "batch_import.py",
    "cognitive_importer.py",
    "generate_report.py",
    "report_generator.py",
    "asrs_dsm_mapper.py",
    
    # Files imported by the core files
    "pdf_cognitive_parser.py",  # Imported by cognitive_importer.py
    "camelot_optimized.py",     # Imported by cognitive_importer.py
    "schema.sql",               # Used for database schema
    "bounding_boxes.csv",       # Used for ASRS parsing
    
    # This script itself
    "move_deprecated_files.py",
    
    # Common directories to keep
    ".venv",
    "__pycache__",
    "data",
    "debug_output",
    "debug_pages",
    "extracted_tables",
    "exports",
    "imgs",
    "parsed",
    "parser",
    "Plans",
    "tests",
    "Bounding_Box_ASRS",
    "worker_scripts",
    "deprecated"
]

# Files to always keep (regardless of extension)
always_keep = [
    ".windsurfrules",
    "cognitive_data.db",
    "tabula-java.jar",
    "README.md",
    "requirements.txt",
    "ToDo.txt",
    "PDS.txt"
]

# File extensions to always keep
keep_extensions = [
    ".pdf",  # Keep all PDF files
    ".db",   # Keep all database files
    ".sql"   # Keep all SQL files
]

def should_keep(filename):
    """Determine if a file should be kept in the main directory."""
    # Check if it's in the essential files list
    if filename in essential_files:
        return True
    
    # Check if it's in the always keep list
    if filename in always_keep:
        return True
    
    # Check if it has an extension we always keep
    for ext in keep_extensions:
        if filename.endswith(ext):
            return True
    
    # Check if it's a directory in the essential list
    if os.path.isdir(filename) and filename in essential_files:
        return True
    
    return False

def main():
    # Ensure the deprecated directory exists
    if not os.path.exists("deprecated"):
        os.makedirs("deprecated")
    
    # Get all files in the current directory
    files = os.listdir(".")
    
    # Count of files moved
    moved_count = 0
    
    # Move non-essential files to the deprecated folder
    for filename in files:
        if not should_keep(filename):
            try:
                # Skip if it's already in the deprecated folder
                if filename.startswith("deprecated"):
                    continue
                
                # Move the file
                shutil.move(filename, os.path.join("deprecated", filename))
                print(f"Moved {filename} to deprecated folder")
                moved_count += 1
            except Exception as e:
                print(f"Error moving {filename}: {e}")
    
    print(f"\nCompleted! Moved {moved_count} files to the deprecated folder.")

if __name__ == "__main__":
    main()

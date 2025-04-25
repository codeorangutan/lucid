import os
import sqlite3

DB_PATH = r"G:\My Drive\Programming\Lucid the App\Project Folder\data\lucid_data.db"
OUTPUT_FILE = "db_check_output.txt"

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(f"Checking database at: {DB_PATH}\n")
    f.write(f"Exists? {os.path.exists(DB_PATH)}\n\n")

    DATA_DIR = os.path.dirname(DB_PATH)
    f.write("Files in data directory:\n")
    for fname in os.listdir(DATA_DIR):
        f.write(f" - {fname}\n")
    f.write("\n")

    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            f.write(f"Tables found: {tables}\n\n")
            # Print schema for each table
            for (table,) in tables:
                f.write(f"--- {table} schema ---\n")
                try:
                    cur.execute(f"PRAGMA table_info({table})")
                    columns = cur.fetchall()
                    for col in columns:
                        f.write(f"  - {col[1]} ({col[2]})\n")
                except Exception as e:
                    f.write(f"  Error reading schema: {e}\n")
                f.write("\n")
            conn.close()
        else:
            f.write("File does not exist at the path above!\n")
    except Exception as e:
        f.write(f"Error opening database: {e}\n")

print(f"Diagnostic output written to {OUTPUT_FILE}")

import sqlite3
import sys
import os

def inspect_db(db_path):
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"\nInspecting database: {db_path}\n")
    # List all tables
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    if not tables:
        print("No tables found in this database.")
        return
    print("Tables:")
    for (table,) in tables:
        print(f"  - {table}")
    print()
    # For each table, print the first 3 rows
    for (table,) in tables:
        print(f"--- {table} (first 3 rows) ---")
        try:
            rows = cursor.execute(f"SELECT * FROM {table} LIMIT 3;").fetchall()
            col_names = [d[0] for d in cursor.description]
            print(" | ".join(col_names))
            for row in rows:
                print(" | ".join(str(x) for x in row))
            if not rows:
                print("  (No data)")
        except Exception as e:
            print(f"  Error reading table: {e}")
        print()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_db.py path/to/database.db")
    else:
        inspect_db(sys.argv[1])

import sqlite3
import sys
import os

def inspect_db_schema(db_path):
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"\nInspecting database schema: {db_path}\n")
    # List all tables
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    if not tables:
        print("No tables found in this database.")
        return
    print("Tables:")
    for (table,) in tables:
        print(f"  - {table}")
    print()
    # For each table, print the schema
    for (table,) in tables:
        print(f"--- {table} schema ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            if not columns:
                print("  (No columns)")
            else:
                print("  | ".join([col[1] + ' (' + col[2] + ')' for col in columns]))
        except Exception as e:
            print(f"  Error reading schema: {e}")
        print()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_db_schema.py path/to/database.db")
    else:
        inspect_db_schema(sys.argv[1])

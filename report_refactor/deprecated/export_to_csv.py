import sqlite3
import csv
from pathlib import Path

DB_PATH = "cognitive_analysis.db"
EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

def get_all_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cur.fetchall()]

def export_table(conn, table_name):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    col_names = [description[0] for description in cur.description]

    output_file = EXPORT_DIR / f"{table_name}.csv"
    with open(output_file, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    print(f"✅ Exported {table_name} → {output_file}")

def main():
    conn = sqlite3.connect(DB_PATH)
    tables = get_all_tables(conn)

    for table in tables:
        export_table(conn, table)

    conn.close()
    print("✅ All tables exported.")

if __name__ == "__main__":
    main()

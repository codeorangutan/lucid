#!/usr/bin/env python3
"""
Check Database Structure

This script examines the structure of the cognitive_analysis.db database
to determine available tables and their schemas.
"""

import os
import sqlite3
import pandas as pd
from pathlib import Path

def main():
    # Get the path to the database
    script_dir = Path(__file__).parent
    db_path = os.path.join(script_dir, "cognitive_analysis.db")
    
    # Check if the database exists
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    print(f"Examining database: {db_path}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("\nAvailable tables:")
        for table in tables:
            print(f"- {table[0]}")
        
        # For each table, get schema information
        print("\nTable schemas:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print(f"\n{table_name} columns:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
        
        # Get row counts for each table
        print("\nRow counts:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"- {table_name}: {count} rows")
        
        # Sample data from each table
        print("\nSample data:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1;")
            sample = cursor.fetchone()
            if sample:
                print(f"\n{table_name} sample row:")
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                for i, col in enumerate(columns):
                    if i < len(sample):
                        print(f"  - {col[1]}: {sample[i]}")
            else:
                print(f"\n{table_name} is empty")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

if __name__ == "__main__":
    main()

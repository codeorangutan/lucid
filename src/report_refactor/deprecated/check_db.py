import sqlite3

def check_database():
    """Check the structure of the database and print table information."""
    conn = sqlite3.connect('cognitive_analysis.db')
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("Tables in database:")
    for table in tables:
        table_name = table[0]
        print(f"- {table_name}")
        
        # Get column info for each table
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print(f"  Columns:")
        for col in columns:
            print(f"    {col[1]} ({col[2]})")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  Row count: {count}")
        print()
    
    conn.close()

if __name__ == "__main__":
    check_database()

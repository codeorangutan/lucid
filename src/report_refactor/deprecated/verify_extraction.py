import sqlite3
import pandas as pd
import os

def display_extracted_subtests(db_path="cognitive_analysis.db"):
    """Display the extracted subtests from the database in a readable format."""
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found!")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        
        # Query all subtests
        query = """
        SELECT patient_id, subtest_name, metric, score, standard_score, percentile
        FROM subtest_results
        ORDER BY subtest_name, metric
        """
        
        # Load into DataFrame for better display
        df = pd.read_sql_query(query, conn)
        
        # Close connection
        conn.close()
        
        if df.empty:
            print("No subtest data found in the database.")
            return
        
        # Display summary by test
        print("\n=== SUMMARY BY TEST ===")
        test_counts = df['subtest_name'].value_counts()
        for test, count in test_counts.items():
            print(f"{test}: {count} subtests")
        
        # Display all subtests grouped by test name
        print("\n=== DETAILED SUBTEST DATA ===")
        for test_name in df['subtest_name'].unique():
            print(f"\n{test_name}:")
            test_df = df[df['subtest_name'] == test_name]
            
            # Format for display
            display_df = test_df[['metric', 'score', 'standard_score', 'percentile']]
            display_df.columns = ['Metric', 'Score', 'Standard', 'Percentile']
            
            # Replace NaN with '-' for better readability
            display_df = display_df.fillna('-')
            
            print(display_df.to_string(index=False))
    
    except Exception as e:
        print(f"Error displaying data: {str(e)}")

if __name__ == "__main__":
    display_extracted_subtests()

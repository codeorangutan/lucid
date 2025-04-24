import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect('cognitive_analysis.db')

# Check ADHD diagnoses
print("\nADHD Diagnoses (first 5 entries):")
diagnoses = pd.read_sql("""
    SELECT * FROM adhd_diagnoses 
    LIMIT 5
""", conn)
print(diagnoses)

# Check criteria distribution
print("\nDSM-5 Criteria Distribution:")
criteria_dist = pd.read_sql("""
    SELECT 
        criterion_id,
        COUNT(*) as total_patients,
        SUM(CASE WHEN criterion_met = 1 THEN 1 ELSE 0 END) as met_count,
        ROUND(AVG(CASE WHEN criterion_met = 1 THEN 1.0 ELSE 0.0 END) * 100, 1) as met_percentage
    FROM dsm5_criteria
    GROUP BY criterion_id
    ORDER BY criterion_id
""", conn)
print(criteria_dist)

# Check ADHD type distribution
print("\nADHD Type Distribution:")
type_dist = pd.read_sql("""
    SELECT 
        adhd_type,
        COUNT(*) as patient_count,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM adhd_diagnoses), 1) as percentage
    FROM adhd_diagnoses
    GROUP BY adhd_type
""", conn)
print(type_dist)

conn.close()

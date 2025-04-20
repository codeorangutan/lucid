import sqlite3

# Connect to the database
conn = sqlite3.connect('cognitive_analysis.db')
cursor = conn.cursor()

# Clear existing Epworth data for patient 40277
cursor.execute('DELETE FROM epworth_total WHERE patient_id = "40277"')
cursor.execute('DELETE FROM epworth_scores WHERE patient_id = "40277"')
conn.commit()

print('Cleared existing Epworth data for patient 40277')

# Close the connection
conn.close()

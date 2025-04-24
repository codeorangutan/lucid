import sqlite3

# Connect to the database
conn = sqlite3.connect('cognitive_analysis.db')
cursor = conn.cursor()

# Check Epworth total scores
cursor.execute('SELECT * FROM epworth_total WHERE patient_id = "40277"')
total_scores = cursor.fetchall()
print(f'Epworth total scores for patient 40277:')
for row in total_scores:
    print(row)

# Check Epworth individual scores
cursor.execute('SELECT COUNT(*) FROM epworth_scores WHERE patient_id = "40277"')
score_count = cursor.fetchone()[0]
print(f'Number of Epworth individual scores for patient 40277: {score_count}')

# Close the connection
conn.close()

import sqlite3

# Connect to the database
conn = sqlite3.connect('cognitive_analysis.db')
cursor = conn.cursor()

# Check NPQ questions
cursor.execute('SELECT COUNT(*) FROM npq_questions WHERE patient_id = "40277"')
question_count = cursor.fetchone()[0]
print(f'NPQ questions for patient 40277: {question_count}')

# Check NPQ domain scores
cursor.execute('SELECT COUNT(*) FROM npq_scores WHERE patient_id = "40277"')
score_count = cursor.fetchone()[0]
print(f'NPQ domain scores for patient 40277: {score_count}')

# Close the connection
conn.close()

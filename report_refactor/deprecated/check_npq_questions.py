import sqlite3

# Connect to the database
conn = sqlite3.connect('cognitive_analysis.db')
cursor = conn.cursor()

# Check total count of NPQ questions for patient 40277
cursor.execute('SELECT COUNT(*) FROM npq_questions WHERE patient_id = "40277"')
total_count = cursor.fetchone()[0]
print(f'NPQ questions for patient 40277: {total_count}')

# Check top 5 domains by question count
cursor.execute('SELECT domain, COUNT(*) FROM npq_questions WHERE patient_id = "40277" GROUP BY domain ORDER BY COUNT(*) DESC LIMIT 5')
print('\nTop 5 domains by question count:')
for row in cursor.fetchall():
    print(f'- {row[0]}: {row[1]} questions')

# Check some sample questions
cursor.execute('SELECT domain, question_number, question_text, score, severity FROM npq_questions WHERE patient_id = "40277" LIMIT 5')
print('\nSample questions:')
for row in cursor.fetchall():
    domain, question_number, question_text, score, severity = row
    print(f'- Domain: {domain}, Q{question_number}: "{question_text[:40]}..." -> {score} - {severity}')

# Close the connection
conn.close()

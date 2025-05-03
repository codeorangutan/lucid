from email_receiver import list_unread_emails_gmail_api

if __name__ == '__main__':
    emails = list_unread_emails_gmail_api(max_results=10)
    for e in emails:
        print(f"Subject: {e['subject']}\nFrom: {e['from']}\nDate: {e['date']}\nSnippet: {e['snippet']}\n{'-'*40}")

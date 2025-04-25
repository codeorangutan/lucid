# Lucid Cognitive Testing Email Automation

## Overview
This application automates the secure receipt, parsing, and processing of cognitive testing referrals via Gmail. It extracts patient and referrer details, logs them in an encrypted database, and supports robust modular workflows.

## Features
- Gmail API integration (OAuth2, secure scopes)
- Regex-based parsing for mobile, email, DOB, ID, etc.
- Filters for "Referral" or "Cognitive Testing" emails
- Automatic reply to referrer
- Secure logging to SQLCipher-encrypted SQLite database
- Modular architecture for easy extension (test triggers, reporting, etc.)
- Docker-ready for deployment

## Requirements
- Python 3.10 (required for SQLCipher support)
- Docker (optional, for containerized deployment)

### Python Dependencies
Install with:
```sh
pip install -r requirements.txt
```

Key packages:
- pysqlcipher3
- sqlalchemy
- google-auth, google-auth-oauthlib, google-auth-httplib2, google-api-python-client
- pytest (for testing)

### System Dependencies (for SQLCipher)
- On Linux/Docker: `libsqlcipher-dev`, `gcc`
- On Windows: Use Python 3.10 and install `pysqlcipher3` via pip

## Usage
1. **Configure Gmail API credentials** in the `credentials/` folder.
2. **Set SQLCipher DB password** (recommended):
   - Windows: `$env:LUCID_DB_PASSWORD="your-strong-password"`
   - Linux/Mac: `export LUCID_DB_PASSWORD="your-strong-password"`
3. **Run the receiver:**
   ```sh
   python src/run_email_receiver.py
   ```
4. **Check logs:**
   - All actions and parsed data are logged to `lucid_email_receiver.log`.
   - Referrals are stored in `lucid_data_encrypted.db` (not tracked by git).

## Docker
Build and run with:
```sh
docker build -t lucid-email .
docker run -e LUCID_DB_PASSWORD=your-strong-password lucid-email
```

## Security Notes
- The database file is encrypted and excluded from git.
- Never log sensitive data in plaintext outside the encrypted DB.
- Use strong passwords and rotate them as needed.

## Modular Design
- All database logic in `src/db.py`
- Email logic in `src/email_receiver.py`
- Easily extendable for test triggers, reporting, and more

## Testing
Run tests with:
```sh
pytest
```

---

For further setup or extension, see comments in the code or contact the maintainer.

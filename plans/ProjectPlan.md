# ✅ LUCID: 50-Step Implementation Plan (Progress Checklist)

## 📋 Brief

LUCID is a healthcare automation app for managing cognitive assessment referrals, maintaining privacy and stealth. The app receives requests, stores data, initiates tests via a browser, monitors completion, reformats reports, and returns them to referrers—while logging all steps securely.

---

## 🧱 Phase 1: Environment & Foundation
- [x] Install Python (latest version) - venv330 - need to .\venv330\Scripts\Activate
- [x] Install pip and virtualenv
- [x] Create project folder and initialize Git
- [x] Add `.gitignore` for sensitive files
- [x] Create `requirements.txt`
- [x] Set up virtual environment and install dependencies
- [x] Install Playwright and run `playwright install`
- [x] Install Docker 
- [x] Create a basic `README.md`
- [x] Create folder structure (`src/`, `tests/`, `data/`, etc.)

---

## 📥 Phase 2: Email Receiver & Parser
- [x] Connect to inbox using `imaplib`
- [x] Fetch unread emails
- [x] Parse for email details comprehensively including timing and referrer
- [x] Test parsing with mock emails
- [X] Mark emails as read
- [ ] Send acknowledgment email to referrer
- [X] Save parsed data to DB

---

## 🗃️ Phase 3: Database Setup
- [X] Design schema: patient number, DOB, email, referrer, status, timestamps
- [X] Set up SQLite with SQLAlchemy
- [ ] Insert parsed email data into database
- [ ] Test data insertion and retrieval
- [ ] Plan migration to `pysqlcipher3` for encryption
- [ ] Address SQLite C wheel issue if needed

---

## 🌐 Phase 4: Test Code Requester (Web Automation)
- [X] Write Playwright script for `cnsvs.com`
- [X] Automate navigation to remote test request form
- [X] Fill in patient number and DOB (Jan 1 YYYY)
- [X] Enter patient email in pop-up
- [X] Submit and confirm form
- [X] Add random delays/mouse events for stealth
- [X] Test with dummy data

---

## 📬 Phase 5: Report Notification Monitoring
- [ ] Consider Flow Control issue of two monitoring scripts
- [X] Extend email parser for report completion
- [X] Parse notification for download link or attachment
- [ ] Download report (PDF)
- [ ] Extract patient ID from PDF
- [X] Mark emails as read
- [ ] Save securely
- [ ] Delete insecure copy if created

---

## 🧾 Phase 6: Report Reformatter
- [ ] Refactor report reformatter to fit with this workflow / pipeline
- [ ] Simplify report for the core features only
- [ ] Respond to notification email triggered workflow to trigger report reformatting
- [x] Reformat contents (CSV to template, cleanup)
- [ ] Add placeholder for interpretation (optional)
- [ ] Load report into DB as Reformatted report
- [ ] Test output format with samples
Using: 
JSON format report 
from src
python report_engine/report_generator_modern.py --json json/40436.json --template "G:\My Drive\Programming\Lucid the App\Project Folder\templates\report_template_radar_bar.html" --output ../output/report_40436.pdf
from root
---python src/report_engine/report_generator_modern.py --json src/json/40436.json --template "G:\My Drive\Programming\Lucid the App\Project Folder\templates\report_template_radar_bar.html" --output output/report_40436.pdf

## 📤 Phase 7: Email Sender
- [ ] Write script to email with attachments (`smtplib`)
- [ ] Optional Encrypt attachments (e.g. GPG, PyCryptodome)
- [ ] Send reformatted report to referrer
- [ ] Log the timing of this email 
- [ ] Test using dummy accounts

---

## 🔄 Phase 8: Orchestrator and Workflow
- [ ] Write main controller script (e.g. FSM or simple pipeline)
- [ ] Update database status at each stage
- [ ] Add error handling and retries
- [ ] Consider adding nagger script to send reminders to patients. This could incluide:
- [ ] Must complete test within 7 days
- [ ] You have 3 days left
- [ ] You have 1 day left
- [ ] You have 12 hours left
- [ ] You have 1 hour left
- [ ] Your test link has expired
- [ ]Current placeholder reminder text
- [ ] Set up 7-day timer with APScheduler or `cron`
- [ ] Auto-send reminder to patient if test not complete

Next Steps:
- [ ] Add/merge the real report reformatter and delivery logic when ready.
- [ ] Integrate actual email/SMS sending for reminders.
- [ ] Set up orchestration scheduling (cron/APScheduler/Task Scheduler).
- [ ] Begin writing and running unit/integration tests for each stage.
- [ ] Continue improving privacy, security, and stealth per your project plan.
- [ ] Dashboard flask scheduler

---

## 🔐 Phase 9: Privacy, Security & Stealth
- [ ] Encrypt PHI at rest and in transit
- [ ] Use TLS for email transmission
- [ ] Scrub all logs of sensitive data
- [ ] Route browser traffic via VPN/proxy
- [ ] Document security policies in `README.md`
- [ ] Add safety limits on request per day, multiple requests for the same patient - currently in orchestrator as warnings


---

## 🚀 Phase 10: Billing Processes
- [ ] Document billing policies in `README.md`
- [ ] Set up billing processes
- [ ] Run monthly report flagging new referrals and making separate invoices for each referrer
- [ ] Store separate billing db for invoices with patient number, date of referral, referrer, status, payment status
- [ ] Send invoices to referrers
- [ ] Mark payments as pending or paid or not billed

---

## 🚀 Phase 11: Testing, Docs, and Deployment
- [ ] Document security policies in `README.md`
- [ ] Purchase Raspberry Pi ? 8GB model + Uninterruptible powersupply
- [ ] Deployment to Raspberry Pi for self-hosting at home
- [ ] Security audit
- [ ] Ensure encrypted SQL deployed
- [ ] Test encrypted SQL
- [ ] Write end-to-end tests with mocks
- [ ] Real patient tests with me as referrer
- [ ] Document full flow for compliance + reproducibility

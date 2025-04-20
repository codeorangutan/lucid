# PowerShell script to set all LUCID Orchestrator stage flags
# Usage: .\set_orch_flags.ps1

# A. Intake: Process New Referrals
# Enable/Disable the stage that fetches and saves new patient referrals from email.
# email, mobile, dob, id_number, subject, body
$env:ORCH_STAGE_INTAKE = "1"

# B. Test Request: Initiate CNS Test
# Enable/Disable the stage that requests CNS cognitive tests for pending patients.
$env:ORCH_STAGE_TEST_REQUEST = "0"

# C. Resend Link Requests: Handle expired test links
# Enable/Disable the stage that handles expired test links.
$env:ORCH_STAGE_RESEND_LINKS = "0"

# D. Report Monitoring: Detect Test Completion
# Enable/Disable the stage that monitors for new CNS VS report notifications (test completion).
$env:ORCH_STAGE_REPORT_MONITOR = "0"

# E. Report Processing: Reformat and Save
# Enable/Disable the stage that reformats downloaded reports and saves them to the database.
$env:ORCH_STAGE_REPORT_PROCESS = "0"

# F. Report Delivery: Email to Referrer
# Enable/Disable the stage that emails completed reports to the referring clinician.
$env:ORCH_STAGE_REPORT_DELIVERY = "0"

# G. Reminders: Nagging for Incomplete Tests
# Enable/Disable the stage that sends reminders to patients with incomplete tests.
$env:ORCH_STAGE_REMINDERS = "0"

Write-Host "All orchestration flags set to 1 (ON)."

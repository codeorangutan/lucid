# Report Generation Pipeline: Executive Summary and PDF Rendering

## Overview
This documentation describes the section of the Lucid App pipeline responsible for generating a cognitive assessment report PDF from structured JSON data and an HTML template. It covers the flow from JSON data to executive summary generation, template injection, and rendering to PDF using Playwright.

---

## Pipeline Steps

### 1. JSON Data Preparation
- **Source:** Data is parsed from uploaded PDFs and stored in a database.
- **Export:** The relevant patient data is exported as a JSON file (see `src/json/40241.json` for example).

### 2. Executive Summary Generation
- **Function:** `generate_adhd_summary(data)` in `scaffold_executive_summary.py`.
- **Input:** Complete patient JSON data.
- **Process:**
  - Extracts key sections: patient info, cognitive scores, subtest results, ASRS, NPQ, DASS, Epworth, etc.
  - Builds a comprehensive, styled HTML executive summary, sectioned for clarity.
  - Returns the summary as an HTML string ready for direct template injection.

### 3. HTML Template Injection
- **Template:** `templates/report_template_sum_valid.html` (and related variants).
- **Placeholder:**
  ```html
  <div id="cognitive-summary-placeholder"> <!-- Summary HTML will be injected here --> </div>
  ```
- **JavaScript Injection:** In the template's `populateReport` function:
  ```js
  if (reportData.cognitive_profile_summary) {
      const summaryElem = document.getElementById('cognitive-summary-placeholder');
      if (summaryElem) {
          summaryElem.innerHTML = reportData.cognitive_profile_summary;
      }
  }
  ```
- **Result:** The executive summary appears in the report at the designated location, styled as intended.

### 4. PDF Rendering with Playwright
- **Script:** `src/report_engine/report_pdf_playwright.py`
- **Process:**
  - Loads the HTML template and injects the patient data (including the executive summary).
  - Applies custom CSS for print and executive summary styling.
  - Renders the fully populated HTML to PDF using Playwright Chromium.
  - Saves a debug HTML file (`*_debug.html`) for troubleshooting.
- **Command Example:**
  ```sh
  python src/report_engine/report_pdf_playwright.py \
      --html "templates/report_template_sum_valid.html" \
      --json "src/json/40241.json" \
      --output "src/json/40241_executive_summary.pdf"
  ```

---

## JSON Data Structure (Key Sections)

- `patient`: Metadata (ID, test status, timestamps, etc.)
- `cognitive_scores`: List of domain scores (domain, scores, percentiles, validity, etc.)
- `subtests`: List of subtest results (test name, metric, score, percentile, validity, etc.)
- `asrs`: ADHD Self-Report responses (question number, response, question text, etc.)
- Other sections may include: `npq_scores`, `npq_questions`, `epworth`, `dass_summary`, `dass_items`, etc.

Example (abridged):
```json
{
  "patient": { "id_number": "40241", ... },
  "cognitive_scores": [ { "domain": "NCI", "percentile": "14.0", ... }, ... ],
  "subtests": [ { "subtest_name": "Verbal Memory Test (VBM)", ... }, ... ],
  "asrs": [ { "question_number": 1, "response": "Often", ... }, ... ]
}
```

---

## Key Points & Best Practices
- The pipeline is modular and each step is self-contained.
- The executive summary is generated as HTML for direct injection (no markdown conversion required).
- Debug HTML output is provided for troubleshooting PDF rendering.
- All data-driven sections (scores, subtests, ASRS, etc.) are dynamically populated from the JSON.
- Custom CSS ensures the executive summary and report are styled for both web and print/PDF.

---

## [2025-05-03 17:46] Refactor Plan & Backup Note

**Refactor Plan:**
- The codebase is being refactored to introduce a normalized patient model (with a `patients` table and robust patient identification) to address issues with patient ID collisions and data linking across sessions/tests.
- All database logic is being centralized in `db.py` to support this, with parsing and import scripts (such as `cognitive_importer.py`) updated to use the new patient-matching logic.
- The refactor is being done incrementally and with test-driven development to avoid breaking the current upload and report generation pipeline.

**Backup Location:**
- Manual backups of all impacted files have been created at the start of the refactor process.
- Backup copies are stored in: `_BACKUP` folder at the root of the project directory (`Project Folder/_BACKUP/`).
- Backed up files include: `src/db.py`, `src/orchestrator.py`, and `src/report_refactor/cognitive_importer.py`.

---

## Extending or Debugging
- To add new sections, update both the summary generation function and the HTML template.
- To troubleshoot rendering, compare the debug HTML and PDF output.
- To add tests, use representative JSON samples and validate both HTML and PDF outputs.

---

*This documentation is auto-generated from a detailed review of the codebase, pipeline, and a sample data file. For further details, see the referenced Python and HTML files in the repository.*

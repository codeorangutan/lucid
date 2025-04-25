# Modern JSON-Based Report Generator: Implementation Plan

## 1. Architecture & File Structure

- `/src/report_engine/`
  - `report_generator_modern.py` (new Python backend, NO legacy code)
  - `templates/`
    - `report_template.html` (your HTML template)
  - `static/` (for CSS, images, etc.)
  - `json/` (input patient data, e.g., `40436.json`)
- `/src/dashboard/` (optional, for future dashboard management)
- `Dockerfile` (for containerization)
- `requirements.txt` (Flask, Jinja2, etc.)

## 2. Core Components

### A. JSON Data Loader
- Loads and validates JSON (from `/src/json/40436.json` or similar)
- Handles missing/invalid fields gracefully

### B. HTML Templating Engine
- Uses Jinja2 (or similar) to render the report using your HTML template and patient JSON data
- Allows easy updates to look/feel via the template

### C. Report Generator Function
- Pure Python function/class:
  `generate_html_report(json_path, template_path, output_path)`
- Reads JSON, renders HTML, saves to file (and/or PDF if needed)

### D. (Optional) PDF Export
- Use `weasyprint`, `wkhtmltopdf`, or similar to convert HTML to PDF if required

### E. CLI Entrypoint
- Script to run report generation from the command line for easy testing

## 3. Testing & TDD
- Unit tests for:
  - JSON loading/validation
  - Template rendering (with sample data)
  - CLI invocation
- Test with your sample file: `/src/json/40436.json`

## 4. Deployment & Dockerization
- Dockerfile to containerize the app with all dependencies
- Expose CLI and/or web endpoint for report generation
- Ready to run on Raspberry Pi (ARM-compatible base image)

## 5. Future: Dashboard Integration
- Flask/FastAPI dashboard for managing report jobs, uploads, downloads, etc.
- Web UI for triggering report generation and viewing results

---

## 🚦 Step-by-Step Roadmap

### Phase 1: Bootstrap the Modern Generator
- [ ] Create `/src/report_engine/` directory and move your HTML template there
- [ ] Implement JSON loader and validator
- [ ] Implement basic Jinja2 template rendering with `/src/json/40436.json`
- [ ] Implement CLI: `python report_generator_modern.py --json src/json/40436.json --template templates/report_template.html --output output/report.html`
- [ ] Add unit tests

### Phase 2: PDF Export (Optional)
- [ ] Integrate HTML-to-PDF (WeasyPrint or wkhtmltopdf)
- [ ] Test PDF output

### Phase 3: Dockerization
- [ ] Write Dockerfile
- [ ] Test build and run on Raspberry Pi

### Phase 4: Dashboard (Optional, Future)
- [ ] Scaffold Flask/FastAPI app for dashboard management
- [ ] Add endpoints for uploading JSON, generating/viewing reports

---

## 🛠️ Next Steps for You

1. **Share your HTML template** (or confirm its filename/location)
2. **Confirm the JSON model** (40436.json is a good starting point—let me know if there are required fields)
3. **Decide on PDF output now or later**
4. **Let me scaffold the initial `/src/report_engine/` structure and the basic generator function**

Would you like me to:
- Scaffold the folder and starter files for you?
- Show a sample Jinja2 template and Python rendering code?
- Help you write the Dockerfile?
- All of the above?

Let me know how you want to proceed or if you want to see a sample code snippet for any step!

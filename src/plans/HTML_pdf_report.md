# HTML-to-PDF Report Module: Summary & Reference

## Overview
This module generates professional cognitive assessment reports by rendering dynamic HTML templates (with charts and tables) and exporting them as PDFs. It is designed for flexibility, modern appearance, and offline/automated use.

## How It Works
1. **JSON Data Input**: Patient data and cognitive scores are provided as JSON files (e.g., `/src/json/40436.json`).
2. **HTML Templating**: Jinja2 is used to inject JSON data into an HTML report template (`/templates/report_template_radar_bar.html`).
3. **Dynamic Charts**: Chart.js (loaded via CDN) renders bar and radar charts directly in the HTML.
4. **PDF Generation**: Playwright (Python) launches a headless Chromium browser, loads the HTML, and exports the rendered page as a PDF. Console logs can be captured for debugging.

## Key Dependencies
- **Python Packages**:
  - `playwright` (for HTML-to-PDF automation)
  - `jinja2` (for HTML templating)
- **JavaScript Libraries**:
  - `Chart.js` (for bar and radar charts)
  - `Tailwind CSS` (for utility-first styling, via CDN or local build)
- **Fonts**: Google Fonts (Inter)

## Color Schemes
### 1. Professional Blue (Current)
- Main background: `#eff6ff` (blue-50)
- Headings: `#1e3a8a` (blue-900)
- Table header: `#dbeafe` (blue-100), text: `#1e3a8a`
- Table even row: `#eff6ff` (blue-50)
- Chart primary: `#2563eb` (blue-600)
- Badges: blues for positive/neutral, orange/red for warning/severity
- Body text: `#334155` (slate-700)

### 2. Backup (Original/Tailwind Default)
- Main background: `#f3f4f6` (gray-100)
- Headings: `#374151` (gray-700)
- Table header: `#f9fafb` (gray-50)
- Chart primary: `#4f46e5` (indigo-600)
- Badges: blue, indigo, purple, pink, red, green, yellow as per Tailwind palette
- Body text: `#4b5563` (gray-600)

See `/templates/color_palette_backup.txt` and `/templates/color_palette_professional.txt` for full details.

## Usage Notes
- **Offline Use**: For offline/production, build Tailwind CSS locally and link as a static CSS file (not CDN).
- **Customization**: Easily adjust colors, fonts, and chart styles in the HTML/CSS template.
- **Debugging**: Playwright can capture browser console logs for troubleshooting chart or data issues.
- **PDF Margins**: Margins can be adjusted in the Playwright script for optimal use of page space.

## File Structure
- `/src/report_engine/report_pdf_playwright.py` – PDF generator script
- `/templates/report_template_radar_bar.html` – Main HTML template
- `/templates/color_palette_backup.txt` – Original color palette
- `/templates/color_palette_professional.txt` – Professional blue palette
- `/src/json/` – Patient data

---
*This module is designed for clarity, flexibility, and professional appearance in clinical cognitive reporting.*

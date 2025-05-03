import asyncio
from playwright.async_api import async_playwright
import json
import os
import sys
from scaffold_executive_summary import generate_adhd_summary
import re

async def generate_pdf(html_path, json_path, output_pdf):
    # Read your JSON data
    # Load JSON, fallback to latin-1 on decode errors
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
    except UnicodeDecodeError:
        with open(json_path, 'r', encoding='latin-1') as f:
            report_data = json.load(f)

    # Generate the executive summary and convert to HTML
    summary_html = generate_adhd_summary(report_data)
    # Already HTML, so no markdown conversion needed
    summary_styled = summary_html
    report_data['cognitive_profile_summary'] = summary_styled

    # --- CSS for executive summary styling ---
    executive_summary_css = '''<style>
    @media print {
        section[aria-labelledby="cognitive-scores-heading"] {
            page-break-before: always;
        }
    }
    /* Readability enhancements */
    .executive-summary p,
    .executive-summary .disclaimer {
        margin-bottom: 0.8em !important;
    }
    .executive-summary ul,
    .executive-summary ol {
        margin: 0.6em 0 1em 1.4em !important;
        padding-left: 1.4em !important;
    }
    .executive-summary li {
        margin-bottom: 0.4em !important;
    }
    .executive-summary h4 {
        color: #1e3a8a !important;
        font-size: 1.1em !important;
        margin: 0.8em 0 0.4em 0 !important;
    }
    .executive-summary {
        background: #f8fafc;
        border-radius: 1.2rem;
        box-shadow: 0 2px 8px rgba(37,99,235,0.06);
        padding: 2.2rem 2.2rem 1.7rem 2.2rem;
        border: 1.5px solid #e0e7ef;
        margin-bottom: 2.5em;
        font-size: 1.13em;
        line-height: 1.6;
        color: #22223b;
    }
    .executive-summary h2, .executive-summary h3, .executive-summary h4 {
        color: #1e293b;
        margin-top: 1.2em;
        margin-bottom: 0.6em;
    }
    .executive-summary ul, .executive-summary ol {
        margin-left: 1.3em;
        margin-bottom: 1em;
    }
    .executive-summary li {
        margin-bottom: 0.2em;
    }
    .executive-summary .highlight {
        background: #ffe066;
        border-radius: 0.3em;
        padding: 0.1em 0.35em;
    }
    .executive-summary strong, .executive-summary b {
        color: #1e293b;
        font-weight: 600;
    }
    .executive-summary .disclaimer {
        margin-bottom: 0.8em !important;
        color: #dc2626 !important;
    }
    .executive-summary-disclaimer {
        font-style: italic !important;
        font-size: 0.93em !important; /* 2pt smaller than 1.13em base */
        display: block;
        line-height: 1.6;
        color: #dc2626 !important;
    }
    .executive-summary ul,
    .executive-summary ol {
        list-style-position: inside;
    }
    .executive-summary li {
        text-indent: -1.2em;
        padding-left: 1.2em;
    }
    .npq-severe-domain {
        background: #fee2e2;
        color: #dc2626;
        border: 1.5px solid #dc2626;
        border-radius: 6px;
        padding: 2px 10px;
        margin-right: 0.3em;
        font-weight: 600;
        display: inline-block;
    }
    .npq-moderate-domain {
        background: #fff7ed;
        color: #b45309;
        border: 1.5px solid #f59e42;
        border-radius: 6px;
        padding: 2px 10px;
        margin-right: 0.3em;
        font-weight: 600;
        display: inline-block;
    }
    </style>'''

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Capture browser console logs for debugging
        def on_console(msg):
            print(f"[BROWSER CONSOLE] {msg.type}: {msg.text}")
        page.on("console", on_console)

        # Load the HTML template file
        await page.goto(f'file://{os.path.abspath(html_path)}')
        # Wait for DOM and key elements
        if html_path.endswith('_embed.html') or html_path.endswith('_valid.html'):
            await page.wait_for_selector("#cognitive-scores-table", timeout=5000)
        else:
            await page.wait_for_selector("#cognitiveBarChart", timeout=5000)
        await page.wait_for_selector("#patient-id", timeout=5000)

        # Inject JSON and call populateReport
        await page.evaluate(f'''
            window.reportData = {json.dumps(report_data)};
            console.log('DEBUG reportData:', window.reportData);
            if (typeof populateReport === "function") populateReport();
        ''')

        # Optionally, wait a bit more to ensure rendering
        await page.wait_for_timeout(1000)

        # Inject consolidated executive summary CSS (add page breaks and compact layout)
        executive_summary_css = '''
@media print {
    /* Ensure new pages before key sections */
    section[aria-labelledby="cognitive-scores-heading"],
    section[aria-labelledby="subtest-results-heading"] {
        page-break-before: always;
    }
    section[aria-labelledby="asrs-dsm-heading"] {
        page-break-before: always;
        page-break-inside: avoid;
    }
}
/* Typography & spacing */
.executive-summary, .executive-summary * {
    font-family: inherit !important;
    color: #334155 !important;
    font-size: 1em !important;
    line-height: 1.55 !important;
}
.executive-summary p,
.executive-summary .disclaimer {
    margin-bottom: 0.8em !important;
}
.executive-summary h4 {
    color: #1e3a8a !important;
    font-size: 1.1em !important;
    margin: 0.8em 0 0.4em 0 !important;
}
/* Lists */
.executive-summary ul,
.executive-summary ol {
    list-style-position: inside !important;
    list-style-type: disc !important;
    margin: 0.6em 0 1em 1.4em !important;
    padding-left: 0 !important;
}
.executive-summary li {
    margin-bottom: 0.4em !important;
    text-indent: -1.2em !important;
    padding-left: 1.2em !important;
}
/* Left border accent */
.executive-summary {
    border-left: 4px solid #2563eb !important;
    padding: 1em !important;
    margin-bottom: 1.5em !important;
}
/* Highlight spans */
.executive-summary .highlight {
    background: #dbeafe !important;
    padding: 0.08em 0.28em !important;
    color: #2563eb !important;
    border-radius: 0.22em !important;
}
/* Bold text */
.executive-summary strong, .executive-summary b {
    color: #2563eb !important;
    font-weight: 600 !important;
}
/* Subtest Results compact spacing */
section[aria-labelledby="subtest-results-heading"] {
    padding: 1rem !important;
    margin-bottom: 1rem !important;
}
#subtest-tables-container {
    display: flex !important;
    flex-direction: column !important;
    gap: 0.5rem !important;
}
#subtest-tables-container > * {
    margin-bottom: 0.5rem !important;
}
/* Further compact subtest tables */
#subtest-tables-container table {
    margin: 0.25em 0 !important;
}
#subtest-tables-container table th,
#subtest-tables-container table td {
    padding-top: 0.25em !important;
    padding-bottom: 0.25em !important;
}
#subtest-tables-container .bar-bg,
#subtest-tables-container .bar-fill {
    height: 0.75em !important;
}
/* Reduce spacing around subtest group headings */
#subtest-tables-container h3 {
    margin: 0.2em 0 !important;
    font-size: 1em !important;
}
/* Remove default margins on subtest table containers */
#subtest-tables-container .overflow-x-auto {
    margin: 0 !important;
    padding: 0 !important;
}
/* ASRS-to-DSM mapping section compact and summary size */
section[aria-labelledby="asrs-dsm-heading"] {
    padding: 1rem !important;
}
#adhd-diagnosis-summary, #adhd-diagnosis-summary-table-container {
    font-size: 0.9em !important;
}
'''
        await page.add_style_tag(content=executive_summary_css)

        # Save the fully rendered HTML (with data injected) as debug HTML
        debug_html_path = os.path.splitext(output_pdf)[0] + '_debug.html'
        rendered_html = await page.content()
        with open(debug_html_path, 'w', encoding='utf-8') as f:
            f.write(rendered_html)
        print(f"[DEBUG] Saved rendered debug HTML (matches PDF) to {debug_html_path}")

        # Save as PDF with reduced margins
        await page.pdf(
            path=output_pdf,
            format="A4",
            print_background=True,
            margin={
                "top": "0mm",
                "bottom": "0mm",
                "left": "0mm",
                "right": "0mm"
            }
        )
        await browser.close()
        print(f"[INFO] PDF generated at {output_pdf}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate PDF from HTML template and JSON using Playwright.")
    parser.add_argument('--html', required=True, help="Path to HTML template file")
    parser.add_argument('--json', required=True, help="Path to JSON data file")
    parser.add_argument('--output', required=True, help="Output PDF file path")
    args = parser.parse_args()
    asyncio.run(generate_pdf(args.html, args.json, args.output))

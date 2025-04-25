import asyncio
from playwright.async_api import async_playwright
import json
import os
import sys

async def generate_pdf(html_path, json_path, output_pdf):
    # Read your JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)

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
        await page.wait_for_selector("#cognitiveBarChart", timeout=5000)
        await page.wait_for_selector("#patient-id", timeout=5000)

        # Inject JSON and call populateReport
        await page.evaluate(f'''
            window.reportData = {json.dumps(report_data)};
            if (typeof populateReport === "function") populateReport();
        ''')

        # Optionally, wait a bit more to ensure rendering
        await page.wait_for_timeout(1000)

        # Save as PDF with reduced margins
        await page.pdf(
            path=output_pdf,
            format="A4",
            print_background=True,
            margin={
                "top": "2mm",
                "bottom": "2mm",
                "left": "2mm",
                "right": "2mm"
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

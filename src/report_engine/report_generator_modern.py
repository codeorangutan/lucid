import argparse
import json
import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def render_report(json_path, template_path, output_pdf_path):
    # Load JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Set up Jinja2 environment (template directory)
    template_dir, template_file = os.path.split(template_path)
    env = Environment(loader=FileSystemLoader(template_dir or '.'))
    template = env.get_template(template_file)

    # Render HTML from template and data
    rendered_html = template.render(report_data=data)

    # Convert HTML to PDF
    HTML(string=rendered_html, base_url=template_dir or '.').write_pdf(output_pdf_path)
    print(f"[INFO] PDF generated at {output_pdf_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate a PDF report from JSON and HTML template")
    parser.add_argument('--json', required=True, help="Path to patient JSON file")
    parser.add_argument('--template', required=True, help="Path to HTML Jinja2 template")
    parser.add_argument('--output', required=True, help="Output PDF file path")
    args = parser.parse_args()
    render_report(args.json, args.template, args.output)

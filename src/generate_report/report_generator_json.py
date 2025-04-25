import os
import json
import logging
from collections import defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Table, TableStyle, Paragraph, Spacer)
from reportlab.lib.units import mm, inch
from json_data_extractor import extract_patient_json
from config_utils import get_lucid_data_db

def get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='NormalSmall', parent=styles['Normal'], fontSize=9, leading=11))
    styles.add(ParagraphStyle(name='ItalicSmall', parent=styles['Italic'], fontSize=9, leading=11, fontName='Helvetica-Oblique'))
    styles.add(ParagraphStyle(name='HeaderSmall', parent=styles['Heading3'], fontSize=11, leading=13, spaceAfter=4))
    return styles

def sanitize_table_data(table_data):
    def sanitize_cell(cell):
        if isinstance(cell, dict):
            return json.dumps(cell, indent=2)
        elif isinstance(cell, list):
            return ", ".join(str(sanitize_cell(x)) for x in cell)
        elif hasattr(cell, 'wrapOn'):
            return cell
        else:
            return str(cell)
    return [
        [sanitize_cell(cell) for cell in row]
        for row in table_data
    ]

def safe_append(elements, item, styles):
    if hasattr(item, 'wrapOn'):
        elements.append(item)
    elif isinstance(item, dict):
        elements.append(Paragraph(json.dumps(item, indent=2), styles['NormalSmall']))
    elif isinstance(item, list):
        for subitem in item:
            safe_append(elements, subitem, styles)
    else:
        elements.append(Paragraph(str(item), styles['NormalSmall']))

def create_section_title(title):
    styles = get_styles()
    return Paragraph(f'<b>{title}</b>', styles['HeaderSmall'])

def draw_logo(canvas, doc):
    pass  # Implement if needed

def generate_report_json(patient_id, output_path, json_dir="json", config=None):
    section_flags = {
        "include_demographics": True,
        "include_cognitive_scores": True,
        "include_subtests": True,
        "include_asrs": True,
        "include_dass": True,
        "include_epworth": True,
        "include_npq": True,
    }
    if config:
        section_flags.update(config)
    os.makedirs(json_dir, exist_ok=True)
    json_path = os.path.join(json_dir, f"{patient_id}.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = extract_patient_json(patient_id)
        if not data:
            raise ValueError(f"No data found for patient {patient_id}")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    filtered_data = {}
    if section_flags["include_demographics"]:
        filtered_data["patient"] = data.get("patient", {})
    if section_flags["include_cognitive_scores"]:
        filtered_data["cognitive_scores"] = data.get("cognitive_scores", [])
    if section_flags["include_subtests"]:
        filtered_data["subtests"] = data.get("subtests", [])
    if section_flags["include_asrs"]:
        filtered_data["asrs"] = data.get("asrs", [])
    if section_flags["include_dass"]:
        filtered_data["dass_summary"] = data.get("dass_summary", [])
        filtered_data["dass_items"] = data.get("dass_items", [])
    if section_flags["include_epworth"]:
        filtered_data["epworth"] = data.get("epworth", {})
    if section_flags["include_npq"]:
        filtered_data["npq_scores"] = data.get("npq_scores", [])
        filtered_data["npq_questions"] = data.get("npq_questions", [])
    create_fancy_report_json(filtered_data, output_path)
    return output_path

def create_fancy_report_json(data, output_path):
    def adjust_canvas(canvas, doc):
        draw_logo(canvas, doc)
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=0.3 * inch,
        rightMargin=0.3 * inch,
        topMargin=0.3 * inch,
        bottomMargin=0.5 * inch
    )
    frame_height = doc.height - (15 * mm)
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin + 5 * mm,
        doc.width,
        frame_height - 5 * mm,
        id='normal'
    )
    patient = data.get("patient", {})
    def footer_json(canvas, doc):
        pid = patient.get("id_number", 'N/A')
        test_date = patient.get("test_date", patient.get("date_of_birth", 'N/A'))
        age = patient.get("age", 'N/A')
        language = patient.get("language", 'N/A')
        footer_text = f"Patient ID: {pid} | Age: {age} | Language: {language} | Test Date: {test_date}"
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(105 * mm, 10 * mm, footer_text)
        canvas.restoreState()
    doc.addPageTemplates([
        PageTemplate(id='AllPages', frames=frame, onPage=footer_json, onPageEnd=adjust_canvas)
    ])
    styles = get_styles()
    elements = []
    heading_text = "Cognitive Profile and ADHD Assessment for Adults"
    heading_style = ParagraphStyle(
        name='CenteredHeading',
        parent=styles["Heading1"],
        alignment=1,
        spaceAfter=6
    )
    heading_para = Paragraph(f"<b>{heading_text}</b>", heading_style)
    heading_table = Table([[heading_para]], colWidths=[doc.width * 0.9])
    heading_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    safe_append(elements, heading_table, styles)
    safe_append(elements, Spacer(1, 12), styles)
    demo_box = []
    demo_box.append(Paragraph("<b>Demographics</b>", styles['Heading2']))
    demo_lines = []
    if patient:
        if "id_number" in patient:
            demo_lines.append(f"Patient ID: {patient['id_number']}")
        if "age" in patient:
            demo_lines.append(f"Age: {patient['age']}")
        if "date_of_birth" in patient:
            demo_lines.append(f"DOB: {patient['date_of_birth']}")
        if "test_date" in patient:
            demo_lines.append(f"Test Date: {patient['test_date']}")
        if "language" in patient:
            demo_lines.append(f"Language: {patient['language']}")
        if "gender" in patient:
            demo_lines.append(f"Gender: {patient['gender']}")
        if "education" in patient:
            demo_lines.append(f"Education: {patient['education']}")
    else:
        demo_lines.append("No patient demographic data available.")
    demo_box.append(Paragraph("<br/>".join(demo_lines), styles['Normal']))
    for item in demo_box:
        safe_append(elements, item, styles)
    safe_append(elements, Spacer(1, 18), styles)
    cognitive_scores = data.get("cognitive_scores", [])
    if cognitive_scores:
        safe_append(elements, create_section_title("Cognitive Domain Scores"), styles)
        score_data = [["Domain", "Standard Score", "Percentile", "Classification", "Valid"]]
        for s in cognitive_scores:
            domain = s.get("domain", s.get("domain_name", ""))
            std_score = s.get("standard_score", "")
            percentile = s.get("percentile", "")
            classification = s.get("classification", "")
            valid = s.get("validity_index", "")
            score_data.append([domain, std_score, percentile, classification, valid])
        t = Table(sanitize_table_data(score_data), colWidths=[110, 80, 80, 80, 60])
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
        ]))
        safe_append(elements, t, styles)
        safe_append(elements, Spacer(1, 12), styles)
    subtests = data.get("subtests", [])
    if subtests:
        safe_append(elements, create_section_title("Subtest Results"), styles)
        grouped = defaultdict(list)
        for row in subtests:
            name = row.get("subtest_name", row.get("name", "Unknown"))
            grouped[name].append(row)
        for subtest, rows in grouped.items():
            safe_append(elements, Paragraph(f"<b>{subtest}</b>", styles['HeaderSmall']), styles)
            table_data = [("Metric", "Score", "Standard Score", "Percentile", "Validity")]
            for r in rows:
                metric = r.get("metric", "")
                score = r.get("score", "")
                std_score = r.get("standard_score", "")
                percentile = r.get("percentile", "")
                validity = r.get("validity", r.get("validity_index", ""))
                table_data.append((metric, score, std_score, percentile, validity))
            t = Table(sanitize_table_data(table_data), colWidths=[140, 60, 80, 60, 60])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            safe_append(elements, t, styles)
            safe_append(elements, Spacer(1, 8), styles)
    asrs = data.get("asrs", [])
    if asrs:
        safe_append(elements, create_section_title("ASRS Results"), styles)
        table_data = [("Question", "Response", "Score")]
        for row in asrs:
            question = row.get("question", "")
            response = row.get("response", "")
            score = row.get("score", "")
            table_data.append((question, response, score))
        t = Table(sanitize_table_data(table_data), colWidths=[320, 80, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        safe_append(elements, t, styles)
        safe_append(elements, Spacer(1, 10), styles)
    dass_summary = data.get("dass_summary", [])
    dass_items = data.get("dass_items", [])
    if dass_summary or dass_items:
        safe_append(elements, create_section_title("DASS Results"), styles)
        if dass_summary:
            table_data = [("Scale", "Score", "Severity")]
            for row in dass_summary:
                scale = row.get("scale", "")
                score = row.get("score", "")
                severity = row.get("severity", "")
                table_data.append((scale, score, severity))
            t = Table(sanitize_table_data(table_data), colWidths=[120, 80, 120])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            safe_append(elements, t, styles)
        if dass_items:
            safe_append(elements, Spacer(1, 6), styles)
            safe_append(elements, Paragraph("<b>DASS Items</b>", styles['HeaderSmall']), styles)
            table_data = [("Item", "Score")] + [ (row.get("item", ""), row.get("score", "")) for row in dass_items ]
            t = Table(sanitize_table_data(table_data), colWidths=[320, 60])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            safe_append(elements, t, styles)
        safe_append(elements, Spacer(1, 10), styles)
    epworth = data.get("epworth", {})
    if epworth:
        safe_append(elements, create_section_title("Epworth Sleepiness Scale"), styles)
        table_data = [("Situation", "Score")]
        for key, value in epworth.items():
            table_data.append((key, value))
        t = Table(sanitize_table_data(table_data), colWidths=[320, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        safe_append(elements, t, styles)
        safe_append(elements, Spacer(1, 10), styles)
    npq_scores = data.get("npq_scores", [])
    npq_questions = data.get("npq_questions", [])
    if npq_scores or npq_questions:
        safe_append(elements, create_section_title("Neuropsychiatric Questionnaire (NPQ)"), styles)
        if npq_scores:
            table_data = [("Domain", "Score", "Severity")]
            for row in npq_scores:
                domain = row.get("domain", "")
                score = row.get("score", "")
                severity = row.get("severity", "")
                table_data.append((domain, score, severity))
            t = Table(sanitize_table_data(table_data), colWidths=[120, 80, 120])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            safe_append(elements, t, styles)
        if npq_questions:
            safe_append(elements, Spacer(1, 6), styles)
            safe_append(elements, Paragraph("<b>NPQ Questions</b>", styles['HeaderSmall']), styles)
            table_data = [("Question", "Response", "Severity")]
            for row in npq_questions:
                question = row.get("question", "")
                response = row.get("response", "")
                severity = row.get("severity", "")
                table_data.append((question, response, severity))
            t = Table(sanitize_table_data(table_data), colWidths=[220, 120, 80])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            safe_append(elements, t, styles)
        safe_append(elements, Spacer(1, 10), styles)
    doc.build(elements)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate cognitive/ADHD report PDF (JSON-based)")
    parser.add_argument('--patient-id', type=str, required=True, help='Patient ID to generate report for')
    parser.add_argument('--output', type=str, required=True, help='Output PDF path')
    args = parser.parse_args()
    generate_report_json(args.patient_id, args.output)
    print(f"[INFO] JSON-based report generated at {args.output}")

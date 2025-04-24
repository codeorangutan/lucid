import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from io import BytesIO
from asrs_dsm_mapper import create_asrs_dsm_section
from reportlab.lib.units import mm, inch

#python generate_report.py 34766-20231015201357.pdf --import

def create_radar_chart(scores):
    labels = [
        "Verbal Memory", "Visual Memory", "Psychomotor Speed",
        "Reaction Time", "Complex Attention", "Cognitive Flexibility",
        "Processing Speed", "Executive Function"
    ]
    values = [scores.get(label, 0) for label in labels]
    values += values[:1]  # loop closure

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)  # Top = 12 o'clock
    ax.set_theta_direction(-1)      # Clockwise

    # Draw colored background bands for standard deviation bands
    bands = [2, 9, 25, 75, 101]  # very low, low, low average, average, above average
    colors_band = ['#ff9999', '#ffcc99', '#ffff99', '#ccffcc', '#b3e6b3']

    for i in range(len(bands)-1):
        ax.fill_between(angles, bands[i], bands[i+1], color=colors_band[i], alpha=0.5)

    # Plot the data points
    ax.plot(angles, values, color='black', linewidth=2)
    ax.fill(angles, values, color='deepskyblue', alpha=0.6)
    
    # Add labels and scores outside the plot
    for angle, value, label in zip(angles[:-1], values[:-1], labels):
        # Convert angle to degrees for easier handling
        deg_angle = np.degrees(angle)
        
        # Calculate positions - increase spacing
        label_radius = 150
        score_radius = 120  # More space between label and score
        
        # Calculate x,y coordinates
        x = label_radius * np.cos(np.radians(deg_angle - 90))
        y = label_radius * np.sin(np.radians(deg_angle - 90))
        
        # Add the label (always horizontal) with larger font
        if ' ' in label:
            label = label.replace(' ', '\n')
        ax.text(angle, label_radius, label,
                ha='center', va='bottom',
                rotation=0,
                fontsize=12,
                fontweight='bold')
        
        # Add the score value below the label
        ax.text(angle, score_radius, f'{int(value)}',
                ha='center', va='top',
                rotation=0,
                fontsize=11)

    ax.set_thetagrids([])  # Remove default labels
    ax.set_ylim(0, 170)  # Increase ylim to accommodate larger text
    ax.set_rgrids([20, 40, 60, 80, 100], labels=['', '', '', '', ''])  # Hide radial labels

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='PNG', dpi=300, bbox_inches='tight', pad_inches=0.5)
    buf.seek(0)
    plt.close(fig)
    return buf

from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

def create_npq_section(data):
    from collections import defaultdict
    elements = []
    styles = getSampleStyleSheet()

    npq_scores = data.get("npq_scores", [])
    npq_questions = data.get("npq_questions", [])

    if not npq_scores:
        return []

    def severity_color(severity):
        s = severity.lower()
        if s == "severe":
            return colors.red
        elif s == "moderate":
            return colors.orange
        elif s == "mild":
            return colors.yellow
        return colors.whitesmoke

    def section_block(title, domains):
        rows = [(title, '', '', '')]
        for domain in domains:
            for row in npq_scores:
                if row[1].lower() == domain.lower():
                    score = row[2]
                    severity = row[3]
                    desc = row[4]
                    color = severity_color(severity)
                    rows.append((domain, score, severity, desc))
                    break
        return rows

    # Section heading + disclaimer
    elements.append(create_section_title("NPQ LF-207 Diagnostic Screen"))
    disclaimer = ("<i>The NPQ is a clinical screening tool. Scores suggest potential symptom burden and are not diagnostic. "
                  "Results should be used as a basis for clinical enquiry rather than diagnosis. "
                  "Clinicians should use these results to guide further assessment and corroborate with clinical judgment.</i>")
    elements.append(Paragraph(disclaimer, styles["Normal"]))
    elements.append(Spacer(1, 12))

    full_table = []

    # Section blocks organized as requested
    full_table += section_block("ADHD", ["ADHD", "Attention", "Impulsive", "Learning", "Memory", "Fatigue", "Sleep"])
    full_table += section_block("Anxiety", ["Anxiety", "Panic", "Agoraphobia", "Obsessions & Compulsions", "Social Anxiety", "PTSD"])
    full_table += section_block("Mood", ["Depression", "Bipolar", "Mood Stability", "Mania", "Aggression"])
    full_table += section_block("ASD", ["Autism", "Asperger's"])
    full_table += section_block("Other", ["Psychotic", "Somatic", "Fatigue", "Suicide", "Pain", "Substance Abuse", "MCI", "Concussion"])

    # Render grouped table
    table_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ])

    # Add color rows
    row_idx = 0
    for row in full_table:
        if len(row) == 4 and row[2]:  # Skip title rows
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), severity_color(row[2]))
        elif len(row) == 4 and not row[2]:  # Section header
            table_style.add('SPAN', (0, row_idx), (-1, row_idx))
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightgrey)
            table_style.add('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.darkblue)
        row_idx += 1

    table = Table(full_table, colWidths=[100, 50, 70, 230])
    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 18))

    # Color legend
    legend_data = [
        ["Severity Color Legend"],
        ["Severe", "Moderate", "Mild", "None"]
    ]
    legend_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('SPAN', (0,0), (-1,0)),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('BACKGROUND', (0,1), (0,1), colors.red),
        ('BACKGROUND', (1,1), (1,1), colors.orange),
        ('BACKGROUND', (2,1), (2,1), colors.yellow),
        ('BACKGROUND', (3,1), (3,1), colors.whitesmoke),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
    ])
    legend_table = Table(legend_data, colWidths=[100, 100, 100, 100])
    legend_table.setStyle(legend_style)
    elements.append(legend_table)
    elements.append(Spacer(1, 18))

    # Full Response Table - using npq_questions instead of npq_responses
    if npq_questions:
        elements.append(create_section_title("Detailed NPQ Responses"))
        
        # Group questions by domain for better organization
        grouped = defaultdict(list)
        for q in npq_questions:
            # Assuming the structure is: id, patient_id, domain, question_number, question_text, score, severity
            domain = q[2]
            question_num = q[3]
            question_text = q[4]
            score = q[5]
            severity = q[6]
            grouped[domain].append((question_num, question_text, score, severity))
        
        # Sort domains alphabetically for consistent presentation
        domains = sorted(grouped.keys())
        
        # Create table with headers
        response_rows = [("Domain", "Question", "Score", "Severity")]
        
        # Add each domain and its questions
        for domain in domains:
            # Add domain header
            response_rows.append((domain, '', '', ''))
            
            # Sort questions by question number
            questions = sorted(grouped[domain], key=lambda x: x[0])
            
            # Add each question
            for q_num, q_text, score, sev in questions:
                response_rows.append(('', f"Q{q_num}: {q_text}", score, sev))
        
        # Create the table with appropriate styling
        resp_table = Table(response_rows, repeatRows=1, colWidths=[80, 280, 40, 60])
        resp_style = TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ])
        
        # Apply styling to rows
        for i, row in enumerate(response_rows[1:], start=1):
            if not row[1]:  # Domain header
                resp_style.add('SPAN', (0, i), (-1, i))
                resp_style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
                resp_style.add('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold')
            else:  # Question row
                severity = row[3]
                resp_style.add('BACKGROUND', (0, i), (-1, i), severity_color(severity))
        
        resp_table.setStyle(resp_style)
        elements.append(resp_table)

    return elements


def draw_logo(canvas, doc):
    logo_path = "imgs/LogoWB.png"
    logo_width = 40 * mm
    logo_height = 40 * mm
    x = doc.pagesize[0] - logo_width - 20  # right margin
    y = doc.pagesize[1] - logo_height - 20  # top margin
    canvas.drawImage(logo_path, x, y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')


def create_section_title(title):
    return Paragraph(f'<b>{title}</b>', getSampleStyleSheet()['Heading2'])


def color_for_percentile(p):
    if p is None:
        return colors.lightgrey
    if p > 74:
        return colors.green
    elif 25 <= p <= 74:
        return colors.lightgreen
    elif 9 <= p < 25:
        return colors.khaki
    elif 2 <= p < 9:
        return colors.orange
    else:
        return colors.red


def create_fancy_report(data, output_path):
    def adjust_canvas(canvas, doc):
        # Fine-tune top margin (adjust the value as needed)
        canvas.setTopMargin(0.2*inch)  # Reduced from default
        canvas.setBottomMargin(0.5*inch)

    doc = SimpleDocTemplate(
            output_path, 
            pagesize=A4, 
            onFirstPage=adjust_canvas,
            onLaterPages=adjust_canvas,
            leftMargin=0.3*inch,
            rightMargin=0.3*inch,
            topMargin=0.3*inch,
            bottomMargin=0.3*inch
    )
    elements = []
    styles = getSampleStyleSheet()

    # Heading centered
    heading_text = "Cognitive Profile and ADHD Assessment for Adults"
    #heading_text = "Cognitive Profile and ADHD Assessment for Adults: Neurocognitive Domains and DSM-5-Aligned ADHD Diagnostic Indicators"
    heading_para = Paragraph(f"<b>{heading_text}</b>", styles["Heading1"])

    # Wrap in a table with fixed width to enable wrapping + centering
    heading_table = Table([[heading_para]], colWidths=[350])  # Max width
    heading_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    elements.append(heading_table)
    elements.append(Spacer(1, 24))

    # Demographics aligned left
    demo_box = []
    demo_box.append(Paragraph("<b>Demographics</b>", styles['Heading2']))

    patient = data["patient"]
    demographics = f"Patient ID: {patient[0]}<br/>Age: {patient[2]}<br/>Language: {patient[3]}<br/>Test Date: {patient[1]}"
    demo_box.append(Paragraph(demographics, styles['Normal']))
    elements.extend(demo_box)
    elements.append(Spacer(1, 18))

    # Validity Check
    invalid_scores = [s for s in data["cognitive_scores"] if s[6] and str(s[6]).lower() == 'no']
    missing_validity = [s for s in data["cognitive_scores"] if not s[6]]

    if invalid_scores:
        elements.append(create_section_title("Validity Check"))
        elements.append(Paragraph("<font color='red'>Warning: Some cognitive tests failed validity checks.</font>", styles['Normal']))
        for s in invalid_scores:
            elements.append(Paragraph(f"Invalid domain: {s[2]}", styles['Normal']))
        elements.append(Spacer(1, 12))

    if missing_validity:
        elements.append(create_section_title("Missing Validity Data"))
        elements.append(Paragraph("<font color='orange'>Warning: Some tests are missing validity index data.</font>", styles['Normal']))
        for s in missing_validity:
            elements.append(Paragraph(f"No validity index: {s[2]}", styles['Normal']))
        elements.append(Spacer(1, 12))

    # Radar Chart
    domain_percentiles = {s[2]: s[4] for s in data["cognitive_scores"] if isinstance(s[4], int)}
    radar_img = create_radar_chart(domain_percentiles)
    elements.append(create_section_title("Cognitive Domain Profile"))
    elements.append(Image(radar_img, width=350, height=350))
    elements.append(Spacer(1, 12))

    # Cognitive Score Table
    if data["cognitive_scores"]:
        print("Cognitive scores:", data["cognitive_scores"])
        elements.append(create_section_title("Cognitive Domain Scores"))
        score_table_data = [("Domain", "Raw Score", "Standard Score", "Percentile")]
        score_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Make header bold
        ]

        for s in data["cognitive_scores"]:
            domain, raw, std, perc = s[2], s[3], s[4], s[5]
            try:
                color = color_for_percentile(perc)
                # Only color the standardized score and percentile cells
                idx = len(score_table_data)
                score_styles.extend([
                    ('BACKGROUND', (2, idx), (2, idx), color),  # Standard Score
                    ('BACKGROUND', (3, idx), (3, idx), color),  # Percentile
                ])
            except Exception:
                print(f"[ERROR] Invalid percentile: {perc} for domain {domain}")
            
            row = [domain, raw, std, perc]
            score_table_data.append(row)

        # Set column widths to better fit the content
        col_widths = [180, 80, 100, 80]  # Adjusted widths
        score_table = Table(score_table_data, colWidths=col_widths)
        score_table.setStyle(TableStyle(score_styles))
        elements.append(score_table)
        elements.append(Spacer(1, 12))
    else:
        print("[WARN] No cognitive_scores found for patient")
        elements.append(Paragraph("Cognitive domain scores were not available.", styles['Normal']))

    # Subtest Results Table
    from collections import defaultdict

    # Subtest Results Table - Nested by test
    elements.append(create_section_title("Subtest Results"))
    if data["subtests"]:
        grouped = defaultdict(list)
        for row in data["subtests"]:
            grouped[row[2]].append((row[3], row[4], row[5], row[6]))  # Metric, Score, Std, Percentile

        table_data = []
        style = [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Make headers bold
        ]

        row_idx = 0
        for test_name, rows in grouped.items():
            # Test header row
            table_data.append([test_name])
            style.append(('SPAN', (0, row_idx), (-1, row_idx)))
            style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightgrey))
            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            row_idx += 1

            # Column header
            table_data.append(['Metric', 'Score', 'Standard', 'Percentile'])
            style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.grey))
            style.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.whitesmoke))
            row_idx += 1

            # Data rows
            for metric, score, std, perc in rows:
                try:
                    color = color_for_percentile(perc)
                    table_data.append([metric, score, std, perc])
                    # Only color standardized score and percentile cells
                    style.extend([
                        ('BACKGROUND', (2, row_idx), (2, row_idx), color),  # Standard Score
                        ('BACKGROUND', (3, row_idx), (3, row_idx), color),  # Percentile
                    ])
                except Exception:
                    print(f"[ERROR] Invalid percentile: {perc} for metric {metric}")
                    table_data.append([metric, score, std, perc])
                row_idx += 1

        # Set column widths to better fit the content
        col_widths = [180, 80, 100, 80]  # Match cognitive scores table
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle(style))
        elements.append(table)
        elements.append(Spacer(1, 12))
    #DSM 5 diagnosis from ASRS
    asrs_responses = {row[2]: row[4] for row in data["asrs"]}
    elements += create_asrs_dsm_section(asrs_responses)

    #NPQ
    elements += create_npq_section(data)

    doc.build(elements, onFirstPage=draw_logo)

    print(f"[INFO] Report saved to {output_path}")

from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# DSM-5 criteria mapped to the actual ASRS question text
DSM5_ASRS_MAPPING = [
    # Criterion A: Inattention
    ("A1: Often fails to give close attention to details or makes careless mistakes", "Q7: How often do you make careless mistakes when you have to work on a boring or difficult project?", 7),
    ("A2: Often has difficulty sustaining attention in tasks or play activities", "Q8: How often do you have difficulty keeping your attention when you are doing boring or repetitive work?", 8),
    ("A3: Often does not seem to listen when spoken to directly", "Q9: How often do you have difficulty concentrating on what people say to you, even when they are speaking to you directly?", 9),
    ("A4: Often does not follow through on instructions and fails to finish duties", "Q1: How often do you have trouble wrapping up the final details of a project, once the challenging parts have been done?", 1),
    ("A5: Often has difficulty organizing tasks and activities", "Q2: How often do you have difficulty getting things in order when you have to do a task that requires organization?", 2),
    ("A6: Often avoids or is reluctant to engage in tasks requiring sustained mental effort", "Q4: When you have a task that requires a lot of thought, how often do you avoid or delay getting started?", 4),
    ("A7: Often loses things necessary for tasks or activities", "Q10: How often do you misplace or have difficulty finding things at home or at work?", 10),
    ("A8: Is often easily distracted by extraneous stimuli", "Q11: How often are you distracted by activity or noise around you?", 11),
    ("A9: Is often forgetful in daily activities", "Q3: How often do you have problems remembering appointments or obligations?", 3),
    
    # Criterion B: Hyperactivity and Impulsivity
    ("B1: Often fidgets or squirms in seat", "Q5: How often do you fidget or squirm with your hands or feet when you have to sit down for a long time?", 5),
    ("B2: Often leaves seat in situations when remaining seated is expected", "Q12: How often do you leave your seat in meetings or other situations in which you are expected to remain seated?", 12),
    ("B3: Often runs about or climbs in situations where it is inappropriate", "Q13: How often do you feel restless or fidgety?", 13),
    ("B4: Often unable to play or engage in leisure activities quietly", "Q14: How often do you have difficulty unwinding and relaxing when you have time to yourself?", 14),
    ("B5: Is often 'on the go', acting as if 'driven by a motor'", "Q6: How often do you feel overly active and compelled to do things, like you were driven by a motor?", 6),
    ("B6: Often talks excessively", "Q15: How often do you find yourself talking too much when you are in social situations?", 15),
    ("B7: Often blurts out an answer before a question has been completed", "Q16: When you're in a conversation, how often do you find yourself finishing the sentences of the people you are talking to, before they can finish them themselves?", 16),
    ("B8: Often has difficulty waiting his or her turn", "Q17: How often do you have difficulty waiting your turn in situations when turn taking is required?", 17),
    ("B9: Often interrupts or intrudes on others", "Q18: How often do you interrupt others when they are busy?", 18)
]

RESPONSE_SCORES = {
    "Never": 0,
    "Rarely": 1,
    "Sometimes": 2,
    "Often": 3,
    "Very Often": 4
}

def is_met(response):
    if response == "N/A":
        return False
    try:
        score = RESPONSE_SCORES.get(response, 0)
        return score >= 2  # Score of 2 or higher is considered "Met"
    except ValueError:
        return False

def create_asrs_dsm_section(asrs_responses):
    styles = getSampleStyleSheet()
    elements = [Paragraph("<b>ASRS to DSM-5 Mapping</b>", styles['Heading2']), Spacer(1, 12)]
    
    # Separate Criterion A and B
    criterion_a_data = [("Criterion A: Inattention", "ASRS Question", "Response", "Met")]
    criterion_b_data = [("Criterion B: Hyperactivity/Impulsivity", "ASRS Question", "Response", "Met")]
    
    met_inattentive = 0
    met_hyperactive = 0

    # Process Criterion A (first 9 items)
    for i in range(9):
        dsm_crit, asrs_text, q_num = DSM5_ASRS_MAPPING[i]
        resp = asrs_responses.get(q_num, "N/A")
        met = "Met" if is_met(resp) else "Not Met"
        if met == "Met":
            met_inattentive += 1
        criterion_a_data.append((Paragraph(dsm_crit, styles['BodyText']), 
                               Paragraph(asrs_text, styles['BodyText']), 
                               resp, met))
    
    # Process Criterion B (last 9 items)
    for i in range(9, 18):
        dsm_crit, asrs_text, q_num = DSM5_ASRS_MAPPING[i]
        resp = asrs_responses.get(q_num, "N/A")
        met = "Met" if is_met(resp) else "Not Met"
        if met == "Met":
            met_hyperactive += 1
        criterion_b_data.append((Paragraph(dsm_crit, styles['BodyText']), 
                               Paragraph(asrs_text, styles['BodyText']), 
                               resp, met))
    
    # Add summary row for Criterion A
    inattention_met = "Met" if met_inattentive >= 5 else "Not Met"
    criterion_a_data.append(("Summary: Criterion A", f"{met_inattentive}/9 criteria met", 
                           f"Need ≥5", inattention_met))
    
    # Add summary row for Criterion B
    hyperactivity_met = "Met" if met_hyperactive >= 5 else "Not Met"
    criterion_b_data.append(("Summary: Criterion B", f"{met_hyperactive}/9 criteria met", 
                           f"Need ≥5", hyperactivity_met))
    
    # Create tables with styling
    table_a = Table(criterion_a_data, repeatRows=1, colWidths=[180, 200, 60, 50])
    style_a = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 0), (3, -1), 'CENTER')
    ]
    
    # Style the Met/Not Met cells for Criterion A
    for idx, row in enumerate(criterion_a_data[1:], start=1):
        if row[3] == "Met":
            style_a.append(('BACKGROUND', (3, idx), (3, idx), colors.green))
        # Special styling for summary row
        if idx == len(criterion_a_data) - 1:
            style_a.append(('BACKGROUND', (0, idx), (0, idx), colors.lightgrey))
            style_a.append(('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold'))
            if row[3] == "Met":
                style_a.append(('BACKGROUND', (3, idx), (3, idx), colors.green))
            else:
                style_a.append(('BACKGROUND', (3, idx), (3, idx), colors.red))
    
    table_a.setStyle(TableStyle(style_a))
    elements.append(table_a)
    elements.append(Spacer(1, 12))
    
    table_b = Table(criterion_b_data, repeatRows=1, colWidths=[180, 200, 60, 50])
    style_b = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 0), (3, -1), 'CENTER')
    ]
    
    # Style the Met/Not Met cells for Criterion B
    for idx, row in enumerate(criterion_b_data[1:], start=1):
        if row[3] == "Met":
            style_b.append(('BACKGROUND', (3, idx), (3, idx), colors.green))
        # Special styling for summary row
        if idx == len(criterion_b_data) - 1:
            style_b.append(('BACKGROUND', (0, idx), (0, idx), colors.lightgrey))
            style_b.append(('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold'))
            if row[3] == "Met":
                style_b.append(('BACKGROUND', (3, idx), (3, idx), colors.green))
            else:
                style_b.append(('BACKGROUND', (3, idx), (3, idx), colors.red))
    
    table_b.setStyle(TableStyle(style_b))
    elements.append(table_b)
    elements.append(Spacer(1, 12))
    
    # Overall diagnosis
    if met_inattentive >= 5 and met_hyperactive >= 5:
        dx = "Combined Presentation"
    elif met_inattentive >= 5:
        dx = "Predominantly Inattentive Presentation"
    elif met_hyperactive >= 5:
        dx = "Predominantly Hyperactive-Impulsive Presentation"
    else:
        dx = "No ADHD Diagnosis Made"
    
    # Create diagnosis table
    diagnosis_data = [
        ["ADHD Diagnosis Summary"],
        ["Inattention", inattention_met],
        ["Hyperactivity/Impulsivity", hyperactivity_met],
        ["Overall Diagnosis", dx]
    ]
    
    diagnosis_table = Table(diagnosis_data, colWidths=[200, 200])
    diagnosis_style = [
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('SPAN', (0, 0), (-1, 0)),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
    ]
    
    # Color the diagnosis cells
    if inattention_met == "Met":
        diagnosis_style.append(('BACKGROUND', (1, 1), (1, 1), colors.green))
    else:
        diagnosis_style.append(('BACKGROUND', (1, 1), (1, 1), colors.red))
        
    if hyperactivity_met == "Met":
        diagnosis_style.append(('BACKGROUND', (1, 2), (1, 2), colors.green))
    else:
        diagnosis_style.append(('BACKGROUND', (1, 2), (1, 2), colors.red))
    
    # Color for overall diagnosis
    if dx != "No ADHD Diagnosis Made":
        diagnosis_style.append(('BACKGROUND', (1, 3), (1, 3), colors.green))
        diagnosis_style.append(('FONTNAME', (1, 3), (1, 3), 'Helvetica-Bold'))
    else:
        diagnosis_style.append(('BACKGROUND', (1, 3), (1, 3), colors.red))
    
    diagnosis_table.setStyle(TableStyle(diagnosis_style))
    elements.append(diagnosis_table)
    elements.append(PageBreak())  # Add page break after ADHD diagnosis
    
    return elements
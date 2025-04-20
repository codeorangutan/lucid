from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

# Questions where "Sometimes" (score of 2) is sufficient to meet criteria
LOWER_THRESHOLD_QUESTIONS = {1, 2, 3, 9, 12, 16, 18}

def is_met(response, question_number):
    """
    Determine if DSM-5 criterion is met based on ASRS response and question number.
    
    Args:
        response: The ASRS response text ("Never", "Rarely", "Sometimes", "Often", "Very Often")
        question_number: The ASRS question number (1-18)
    
    Returns:
        bool: True if criterion is met, False otherwise
    """
    if response == "N/A":
        return False
    try:
        score = RESPONSE_SCORES.get(response, 0)
        # For specific questions, "Sometimes" (2) is sufficient
        # For all other questions, need "Often" (3) or "Very Often" (4)
        required_score = 2 if question_number in LOWER_THRESHOLD_QUESTIONS else 3
        return score >= required_score
    except ValueError:
        return False

def create_asrs_dsm_section(asrs_responses):
    styles = getSampleStyleSheet()
    
    # Create a style for wrapped text with word wrap enabled and reduced spacing
    wrapped_style = ParagraphStyle(
        'WrappedText',
        parent=styles['BodyText'],
        fontSize=9,
        wordWrap='CJK',
        leading=10,  # Reduced line spacing
        spaceBefore=0,
        spaceAfter=0
    )
    
    # Create a style for response and met columns
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['BodyText'],
        fontSize=9,
        alignment=1,  # Center alignment
        spaceBefore=0,
        spaceAfter=0
    )
    
    elements = []
    elements.extend([Paragraph("<b>ASRS to DSM-5 Mapping</b>", styles['Heading2']), Spacer(1, 6)])
    
    # Separate Criterion A and B
    criterion_a_data = [("Criterion A: Inattention", "ASRS Question", "Response", "Met")]
    criterion_b_data = [("Criterion B: Hyperactivity/Impulsivity", "ASRS Question", "Response", "Met")]
    
    met_inattentive = 0
    met_hyperactive = 0

    # Process Criterion A (first 9 items)
    for i in range(9):
        dsm_crit, asrs_text, q_num = DSM5_ASRS_MAPPING[i]
        resp = asrs_responses.get(q_num, "N/A")
        met = "Met" if is_met(resp, q_num) else "Not Met"
        if met == "Met":
            met_inattentive += 1
        criterion_a_data.append((
            Paragraph(dsm_crit, wrapped_style),
            Paragraph(asrs_text, wrapped_style),
            Paragraph(resp, cell_style),
            Paragraph(met, cell_style)
        ))
    
    # Process Criterion B (last 9 items)
    for i in range(9, 18):
        dsm_crit, asrs_text, q_num = DSM5_ASRS_MAPPING[i]
        resp = asrs_responses.get(q_num, "N/A")
        met = "Met" if is_met(resp, q_num) else "Not Met"
        if met == "Met":
            met_hyperactive += 1
        criterion_b_data.append((
            Paragraph(dsm_crit, wrapped_style),
            Paragraph(asrs_text, wrapped_style),
            Paragraph(resp, cell_style),
            Paragraph(met, cell_style)
        ))
    
    # Add summary row for Criterion A
    inattention_met = "Met" if met_inattentive >= 5 else "Not Met"
    criterion_a_data.append(("Summary: Criterion A", f"{met_inattentive}/9 criteria met", 
                           f"Need ≥5", inattention_met))
    
    # Add summary row for Criterion B
    hyperactivity_met = "Met" if met_hyperactive >= 5 else "Not Met"
    criterion_b_data.append(("Summary: Criterion B", f"{met_hyperactive}/9 criteria met", 
                           f"Need ≥5", hyperactivity_met))
    
    # Create tables with styling - wider columns and reduced padding
    table_a = Table(criterion_a_data, repeatRows=1, colWidths=[190, 230, 50, 50])
    style_a = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 0), (3, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Bold headers
        ('LEFTPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    
    # Style the Met/Not Met cells for Criterion A
    for idx, row in enumerate(criterion_a_data[1:], start=1):
        if row[3] == "Met" or (isinstance(row[3], Paragraph) and row[3].text == "Met"):
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
    elements.append(Spacer(1, 6))
    
    table_b = Table(criterion_b_data, repeatRows=1, colWidths=[190, 230, 50, 50])
    style_b = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 0), (3, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Bold headers
        ('LEFTPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    
    # Style the Met/Not Met cells for Criterion B
    for idx, row in enumerate(criterion_b_data[1:], start=1):
        if row[3] == "Met" or (isinstance(row[3], Paragraph) and row[3].text == "Met"):
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
    elements.append(Spacer(1, 6))
    
    # Overall diagnosis
    if met_inattentive >= 5 and met_hyperactive >= 5:
        dx = "Combined Presentation"
    elif met_inattentive >= 5:
        dx = "Predominantly Inattentive Presentation"
    elif met_hyperactive >= 5:
        dx = "Predominantly Hyperactive-Impulsive Presentation"
    else:
        dx = "No ADHD Diagnosis Made"
    
    # Create diagnosis table - adjusted widths
    diagnosis_data = [
        ["ADHD Diagnosis Summary"],
        ["Inattention", inattention_met],
        ["Hyperactivity/Impulsivity", hyperactivity_met],
        ["Overall Diagnosis", dx]
    ]
    
    diagnosis_table = Table(diagnosis_data, colWidths=[190, 230])
    diagnosis_style = [
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('SPAN', (0, 0), (-1, 0)),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),  # Consistent font size
        ('LEFTPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
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
    
    # Wrap ASRS section in KeepTogether
    asrs_elements = KeepTogether(elements)
    
    # Return elements with page break after ASRS section
    return [asrs_elements, PageBreak()]
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

def create_npq_section(data):
    from collections import defaultdict
    elements = []
    styles = get_styles()

    npq_scores = data.get("npq_scores", [])
    npq_questions = data.get("npq_questions", [])

    if not npq_scores:
        return []

    def severity_color(severity):
        s = severity.lower() if isinstance(severity, str) else str(severity)
        if s == "severe":
            return colors.red
        elif s == "moderate":
            return colors.orange
        elif s == "mild":
            return colors.yellow
        return colors.whitesmoke

    def section_block(title, domains):
        # Make section headers more distinct
        header = f"=== {title} Symptoms ==="
        rows = [(header,)]  # Section header with clear formatting
        for domain in domains:
            for row in npq_scores:
                # Use correct domain index (3) for matching
                if isinstance(row[3], str) and row[3].lower() == domain.lower():
                    score = row[4]
                    severity = row[5]
                    color = severity_color(severity)
                    rows.append((domain, score, severity))
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


def get_npq_impacted_domains(npq_scores, min_severity_level=2):
    """Identifies NPQ domains with moderate or higher severity."""
    # min_severity_level: 1=Mild, 2=Moderate, 3=Severe
    impacted = []
    severity_map = {"Not a problem": 0, "A mild problem": 1, "Mild": 1,
                    "A moderate problem": 2, "Moderate": 2,
                    "A severe problem": 3, "Severe": 3}

    for score in npq_scores:
        if score.get('severity') and score['severity'] in severity_map:
             # Check if severity meets the minimum threshold (default: Moderate)
            current_severity_level = severity_map[score['severity']]
            if current_severity_level >= min_severity_level:
                if "Average" not in score['domain']: # Exclude summary scores
                     severity_text = score['severity'].replace("A ", "").replace(" problem", "").capitalize()
                     impacted.append(f"{score['domain']} ({severity_text})")

    impacted.sort()
    return impacted

def get_severe_npq_symptoms(npq_questions, min_severity_score=2):
    """Identifies specific NPQ questions rated as moderate or severe (default) and removes duplicates. Severe symptoms are listed first."""
    severe = []
    moderate = []
    seen = set()
    severity_map = {"Not a problem": 0, "A mild problem": 1, "Mild": 1,
                    "A moderate problem": 2, "Moderate": 2,
                    "A severe problem": 3, "Severe": 3}

    for q in npq_questions:
        if q.get('severity') and q['severity'] in severity_map:
            if severity_map[q['severity']] >= min_severity_score:
                severity_text = q['severity'].replace("A ", "").replace(" problem", "").capitalize()
                symptom_text = f"{q['question_text']} ({severity_text})"
                if symptom_text not in seen:
                    if severity_map[q['severity']] == 3:
                        severe.append(symptom_text)
                    else:
                        moderate.append(symptom_text)
                    seen.add(symptom_text)

    # Severe first, then moderate
    severe.sort()
    moderate.sort()
    return severe + moderate

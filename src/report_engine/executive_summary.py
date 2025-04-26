import json
import sys
from collections import Counter

# --- Helper Functions (Updated/Expanded) ---

TEMPLATE_PATH = "g:/My Drive/Programming/Lucid the App/Project Folder/src/report_engine/executive_summary_template_v2.md"

def get_score_range(percentile):
    """Categorizes percentile score into descriptive ranges."""
    if percentile is None: return "N/A"
    try:
        p = float(percentile)
        if p >= 98: return "Very Superior"
        elif p >= 91: return "Superior"
        elif p >= 75: return "High Average"
        elif p >= 25: return "Average"
        elif p >= 9: return "Low Average"
        elif p >= 2: return "Borderline Impaired"
        else: return "Impaired"
    except (ValueError, TypeError):
        return "N/A"

def format_score_entry(item, score_type='cognitive'):
    """Formats cognitive or subtest score entries, checking validity."""
    domain = item.get('domain') if score_type == 'cognitive' else f"{item.get('subtest_name', '')} - {item.get('metric', '')}"
    percentile = item.get('percentile')
    is_valid = False

    # Check validity based on score type
    if score_type == 'cognitive':
        # Check 'validity_index' field for cognitive scores
        is_valid = item.get('validity_index', '').strip().lower() == 'yes'
    elif score_type == 'subtest':
         # Check 'validity_flag' field for subtests (assuming 1 means valid)
        is_valid = item.get('validity_flag') == 1

    if not is_valid:
        # Return None or a specific string if invalid, prevents processing
        # print(f"Skipping invalid score: {domain}") # Optional: for debugging
        return None # Do not include invalid scores in the output lists

    if percentile is None: return None # Skip if no percentile data even if valid

    try:
        p = float(percentile)
        # Only return formatted string if valid and percentile exists
        return f"{domain} (Percentile: {p:.1f}, Range: {get_score_range(p)})"
    except (ValueError, TypeError):
         # Handle non-numeric percentiles gracefully for valid entries
        return f"{domain} (Percentile: {percentile}, Range: Error processing)"

def get_cognitive_scores_by_percentile(cognitive_scores, min_percentile=75, max_percentile=16):
    """Categorizes *valid* cognitive domains into strengths and weaknesses."""
    strengths = []
    weaknesses = []
    skip_domains = ["Neurocognition Index (NCI)", "Composite Memory"]

    for score in cognitive_scores:
        if score.get('domain') in skip_domains: continue

        # format_score_entry now includes the validity check
        formatted_entry = format_score_entry(score, score_type='cognitive')
        if not formatted_entry: continue # Skip if invalid or missing percentile

        # Proceed with categorization only if entry is valid and formatted
        try:
            # Extract percentile from the formatted string for reliable comparison
            percentile_str = formatted_entry.split('Percentile: ')[1].split(',')[0]
            percentile = float(percentile_str)

            if percentile >= min_percentile:
                strengths.append(formatted_entry)
            elif percentile <= max_percentile:
                weaknesses.append(formatted_entry)
        except (ValueError, TypeError, IndexError):
             # Handle potential errors extracting percentile from string
            print(f"Warning: Could not process percentile for entry: {formatted_entry}")
            continue

    # Sort by percentile
    strengths.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]), reverse=True)
    weaknesses.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]))

    return strengths, weaknesses

def get_notable_subtest_scores(subtests, min_percentile=91, max_percentile=9):
    """Identifies notable *valid* subtest metrics (very high or very low percentiles)."""
    notable_scores = []
    for subtest in subtests:
        # format_score_entry now includes the validity check
        formatted_entry = format_score_entry(subtest, score_type='subtest')
        if not formatted_entry: continue # Skip if invalid or missing percentile

        # Proceed with categorization only if entry is valid and formatted
        try:
             # Extract percentile from the formatted string
            percentile_str = formatted_entry.split('Percentile: ')[1].split(',')[0]
            percentile = float(percentile_str)

            if percentile >= min_percentile or percentile <= max_percentile:
                 notable_scores.append(formatted_entry)
        except (ValueError, TypeError, IndexError):
            print(f"Warning: Could not process percentile for entry: {formatted_entry}")
            continue

    # Sort by percentile, ascending
    notable_scores.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]))
    return notable_scores

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
    """Identifies specific NPQ questions rated as moderate or severe (default) and removes duplicates."""
    severe_symptoms = []
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
                    severe_symptoms.append(symptom_text)
                    seen.add(symptom_text)

    severe_symptoms.sort()
    return severe_symptoms

def generate_cognitive_profile_summary(data):
    """
    Generate the cognitive profile executive summary from JSON data.
    Returns the summary as a markdown string (can be converted to HTML by caller).
    """
    # Basic Info
    patient_id = data.get('patient', {}).get('id_number', 'N/A')
    test_date = data.get('patient', {}).get('test_completed', 'N/A')

    # ADHD Screening Logic (Unchanged from previous version)
    adhd_presentation = None
    inattention_met_count = 0
    hyperactivity_met_count = 0
    adhd_screening_outcome_statement = "ASRS/DSM-5 alignment data not available."
    adhd_criteria_details = ""
    summary_adhd_screening_outcome = "ASRS/DSM-5 alignment was not assessed or data is missing."
    recommendation_focus_adhd = ""

    if data.get('dass_summary') and data.get('dass_items'):
        adhd_presentation = data['dass_summary'][0].get('diagnosis')
        for item in data['dass_items']:
            if item.get('is_met') == 1:
                if item['dsm_category'] == 'Inattention': inattention_met_count += 1
                elif item['dsm_category'] == 'Hyperactivity/Impulsivity': hyperactivity_met_count += 1

        meets_inattention_criteria = inattention_met_count >= 5
        meets_hyperactivity_criteria = hyperactivity_met_count >= 5

        if adhd_presentation and "Unknown" not in adhd_presentation and (meets_inattention_criteria or meets_hyperactivity_criteria):
             adhd_screening_outcome_statement = f"Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening suggests a presentation consistent with **{adhd_presentation}**."
             adhd_criteria_details = (f"* Endorsed symptoms met criteria for **{inattention_met_count}/9 Inattention** domains.\n"
                                      f"* Endorsed symptoms met criteria for **{hyperactivity_met_count}/9 Hyperactivity/Impulsivity** domains.")
             summary_adhd_screening_outcome = f"symptom screening was consistent with an **{adhd_presentation}** profile, meeting criteria for {inattention_met_count}/9 inattention and {hyperactivity_met_count}/9 hyperactivity/impulsivity symptoms."
             recommendation_focus_adhd = "confirm the potential ADHD presentation"
        elif meets_inattention_criteria or meets_hyperactivity_criteria:
             adhd_screening_outcome_statement = "Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening indicates a significant number of endorsed ADHD-related symptoms, but a specific presentation was not determined by this screener."
             adhd_criteria_details = (f"* Endorsed symptoms met criteria for **{inattention_met_count}/9 Inattention** domains.\n"
                                     f"* Endorsed symptoms met criteria for **{hyperactivity_met_count}/9 Hyperactivity/Impulsivity** domains.")
             summary_adhd_screening_outcome = f"symptom screening indicated clinically significant ADHD-related symptoms ({inattention_met_count}/9 inattention, {hyperactivity_met_count}/9 hyperactivity/impulsivity), warranting further investigation."
             recommendation_focus_adhd = "clarify a potential ADHD presentation"
        else:
            adhd_screening_outcome_statement = "Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening **did not meet the threshold criteria** for an ADHD presentation."
            adhd_criteria_details = (f"* Endorsed symptoms aligned with **{inattention_met_count}/9 Inattention** criteria.\n"
                                     f"* Endorsed symptoms aligned with **{hyperactivity_met_count}/9 Hyperactivity/Impulsivity** criteria.")
            summary_adhd_screening_outcome = f"symptom screening did not meet threshold criteria for an ADHD presentation ({inattention_met_count}/9 inattention, {hyperactivity_met_count}/9 hyperactivity/impulsivity)."
            recommendation_focus_adhd = ""

    # Cognitive Performance (Now checks validity)
    nci_score = "N/A"
    nci_percentile = "N/A"
    nci_range = "N/A"
    list_of_cognitive_strengths = "N/A"
    list_of_cognitive_weaknesses = "N/A"
    list_of_notable_subtest_scores = "N/A"
    summary_cognitive_profile = "Cognitive performance was not assessed or data is missing."
    invalid_domains_skipped = [] # To potentially note skipped domains if needed, but not added to template

    if data.get('cognitive_scores'):
        # Check NCI validity separately as it's handled differently
        nci_data = next((item for item in data['cognitive_scores'] if item['domain'] == 'Neurocognition Index (NCI)'), None)
        if nci_data:
            nci_valid = nci_data.get('validity_index', '').strip().lower() == 'yes'
            if nci_valid:
                nci_score = nci_data.get('standard_score', 'N/A')
                nci_percentile = nci_data.get('percentile', 'N/A')
                nci_range = get_score_range(nci_percentile)
            else:
                nci_range = "Invalid"
                nci_score = "Invalid"
                nci_percentile = "Invalid"
                invalid_domains_skipped.append("Neurocognition Index (NCI)")

        # Pass the full list to the helper which now filters validity internally
        strengths, weaknesses = get_cognitive_scores_by_percentile(data['cognitive_scores'])
        list_of_cognitive_strengths = "\n".join([f"* {s}" for s in strengths]) if strengths else "No specific *valid* strengths noted (>= 75th percentile)."
        list_of_cognitive_weaknesses = "\n".join([f"* {w}" for w in weaknesses]) if weaknesses else "No specific *valid* weaknesses noted (<= 16th percentile)."

        # Update summary based on valid NCI
        if nci_range != "Invalid":
             strength_summary = f"strengths in {', '.join([s.split(' (Percentile:')[0] for s in strengths])}" if strengths else "no specific high-performing areas"
             weakness_summary = f"weaknesses in {', '.join([w.split(' (Percentile:')[0] for w in weaknesses])}" if weaknesses else "no specific low-performing areas"
             summary_cognitive_profile = f"overall *valid* cognitive performance (NCI) was in the {nci_range.lower()} range, with {strength_summary.lower()} and relative {weakness_summary.lower()} noted in valid domains."
        else:
             summary_cognitive_profile = "the overall cognitive index (NCI) was invalid. Analysis focused on individual valid domains."
             # Potentially add summary of valid strengths/weaknesses if NCI is invalid but others are valid
             if strengths or weaknesses:
                 strength_summary = f"valid strengths in {', '.join([s.split(' (Percentile:')[0] for s in strengths])}" if strengths else "no specific high-performing areas"
                 weakness_summary = f"valid weaknesses in {', '.join([w.split(' (Percentile:')[0] for w in weaknesses])}" if weaknesses else "no specific low-performing areas"
                 summary_cognitive_profile += f" Within validly assessed domains, {strength_summary.lower()} and relative {weakness_summary.lower()} were observed."


    if data.get('subtests'):
        # Helper function now filters validity internally
        notable_subtests = get_notable_subtest_scores(data['subtests'])
        list_of_notable_subtest_scores = "\n".join([f"* {s}" for s in notable_subtests]) if notable_subtests else "No *valid* subtest scores reached notable highs (>= 91st percentile) or lows (<= 9th percentile)."
    else:
         list_of_notable_subtest_scores = "Subtest data not available."


    # NPQ Symptoms (Focus on Moderate/Severe)
    list_of_npq_impacted_domains = "NPQ scores not available."
    list_of_severe_npq_symptoms = "NPQ questions not available."
    summary_npq_findings = "Self-reported symptoms via NPQ were not assessed or data is missing."
    recommendation_focus_npq = ""

    if data.get('npq_scores'):
        # Get domains rated Moderate or Severe (min_severity_level=2)
        impacted_domains = get_npq_impacted_domains(data['npq_scores'], min_severity_level=2)
        list_of_npq_impacted_domains = "\n".join([f"* {d}" for d in impacted_domains]) if impacted_domains else "No domains reported with Moderate or greater severity."

        impacted_domain_names = [d.split(' (')[0] for d in impacted_domains]
        if impacted_domain_names:
            summary_npq_findings = f"the NPQ highlighted concerns rated **Moderate or Severe** in areas including {', '.join(impacted_domain_names[:4]).lower()}{'...' if len(impacted_domain_names) > 4 else '.'}"
            recommendation_focus_npq = f"assess the reported moderate/severe {', '.join(impacted_domain_names[:2]).lower()} symptoms"
        else:
            summary_npq_findings = "the NPQ did not indicate significant concerns rated Moderate or Severe in the surveyed domains."


    if data.get('npq_questions'):
         # Get specific symptoms rated Moderate or Severe (min_severity_score=2)
        severe_symptoms = get_severe_npq_symptoms(data['npq_questions'], min_severity_score=2)
        list_of_severe_npq_symptoms = "\n".join([f"* {s}" for s in severe_symptoms]) if severe_symptoms else "No specific symptoms reported as Moderate or Severe."
    else:
         list_of_severe_npq_symptoms = "NPQ detailed responses not available."


    # Epworth Sleepiness Scale (Unchanged)
    optional_epworth_summary = ""
    summary_sleepiness = ""
    recommendation_focus_sleep = ""
    if data.get('epworth') and data['epworth'].get('summary'):
        epworth_summary_data = data['epworth']['summary'][0]
        epworth_score = epworth_summary_data.get('total_score')
        epworth_interpretation = epworth_summary_data.get('interpretation', '').strip('.')
        if epworth_score is not None and epworth_interpretation:
            optional_epworth_summary = f"The Epworth Sleepiness Scale indicated **{epworth_interpretation}** (Total Score: {epworth_score})."
            if "moderate" in epworth_interpretation.lower() or "excessive" in epworth_interpretation.lower() or "severe" in epworth_interpretation.lower():
                 summary_sleepiness = f"Potential {epworth_interpretation.lower()} was also noted."
                 recommendation_focus_sleep = "evaluate potential sleep-related issues"


    # Construct Final Recommendation Sentence (Unchanged)
    rec_parts = [part for part in [recommendation_focus_adhd, recommendation_focus_npq, recommendation_focus_sleep] if part]
    if not rec_parts:
        recommendation_focus = "further explore the patient's functioning and any reported concerns"
    elif len(rec_parts) == 1:
        recommendation_focus = rec_parts[0]
    else:
        recommendation_focus = ", ".join(rec_parts[:-1]) + (" and " if len(rec_parts) > 1 else "") + rec_parts[-1]


    # Load the v2 template instead of the default
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()

    # Fill the template
    summary = template.format(
        patient_id=patient_id,
        test_date=test_date,
        adhd_screening_outcome_statement=adhd_screening_outcome_statement,
        adhd_criteria_details=adhd_criteria_details,
        nci_range=nci_range,
        nci_score=nci_score,
        nci_percentile=nci_percentile,
        list_of_cognitive_strengths=list_of_cognitive_strengths,
        list_of_cognitive_weaknesses=list_of_cognitive_weaknesses,
        list_of_notable_subtest_scores=list_of_notable_subtest_scores,
        list_of_npq_impacted_domains=list_of_npq_impacted_domains,
        list_of_severe_npq_symptoms=list_of_severe_npq_symptoms,
        optional_epworth_summary=optional_epworth_summary,
        summary_adhd_screening_outcome=summary_adhd_screening_outcome,
        summary_cognitive_profile=summary_cognitive_profile,
        summary_npq_findings=summary_npq_findings,
        summary_sleepiness=summary_sleepiness,
        recommendation_focus=recommendation_focus
    )
    return summary

# --- CLI/testing block ---
if __name__ == "__main__":
    import sys
    # Accept JSON path as argument, default to correct location
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = '../json/40436.json'  # Default to correct relative path
    with open(file_path, 'r') as f:
        data = json.load(f)
    summary = generate_cognitive_profile_summary(data)
    # Save the populated summary to a new output file (do not overwrite template)
    output_file_name = "executive_summary_output.md"
    with open(output_file_name, "w") as f:
        f.write(summary)
    print(f"Populated summary saved to {output_file_name}")
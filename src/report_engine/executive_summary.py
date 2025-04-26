import json
from collections import Counter

# --- Helper Functions (Updated/Expanded) ---

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
    """Formats cognitive or subtest score entries."""
    domain = item.get('domain') if score_type == 'cognitive' else f"{item.get('subtest_name', '')} - {item.get('metric', '')}"
    percentile = item.get('percentile')
    if percentile is None: return None # Skip if no percentile data
    try:
        p = float(percentile)
        return f"{domain} (Percentile: {p:.1f}, Range: {get_score_range(p)})"
    except (ValueError, TypeError):
        return f"{domain} (Percentile: {percentile}, Range: Error processing)" # Handle non-numeric gracefully

def get_cognitive_scores_by_percentile(cognitive_scores, min_percentile=75, max_percentile=16):
    """Categorizes cognitive domains into strengths and weaknesses based on percentiles."""
    strengths = []
    weaknesses = []
    skip_domains = ["Neurocognition Index (NCI)", "Composite Memory"] # Usually reported separately

    for score in cognitive_scores:
        if score.get('domain') in skip_domains: continue

        formatted_entry = format_score_entry(score, score_type='cognitive')
        if not formatted_entry: continue

        try:
            percentile = float(score.get('percentile', -1)) # Use -1 to handle missing correctly
            if percentile >= min_percentile:
                strengths.append(formatted_entry)
            elif percentile <= max_percentile:
                weaknesses.append(formatted_entry)
        except (ValueError, TypeError):
            continue # Skip non-numeric percentiles safely

    # Sort by percentile (descending for strengths, ascending for weaknesses)
    strengths.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]), reverse=True)
    weaknesses.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]))

    return strengths, weaknesses

def get_notable_subtest_scores(subtests, min_percentile=91, max_percentile=9):
    """Identifies notable subtest metrics (very high or very low percentiles)."""
    notable_scores = []
    for subtest in subtests:
        formatted_entry = format_score_entry(subtest, score_type='subtest')
        if not formatted_entry: continue

        try:
            percentile = float(subtest.get('percentile', 50)) # Use 50 to handle missing correctly
            if percentile >= min_percentile or percentile <= max_percentile:
                 notable_scores.append(formatted_entry)
        except (ValueError, TypeError):
            continue

    # Sort by percentile, ascending
    notable_scores.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]))
    return notable_scores

def get_npq_impacted_domains(npq_scores):
    """Identifies NPQ domains with mild or higher severity."""
    impacted = []
    # Severity mapping: 0 = Not a problem, 1 = Mild, 2 = Moderate, 3 = Severe
    severity_map = {"Not a problem": 0, "A mild problem": 1, "Mild": 1,
                    "A moderate problem": 2, "Moderate": 2,
                    "A severe problem": 3, "Severe": 3}

    for score in npq_scores:
        # Check if 'severity' key exists and is mappable
        if score.get('severity') and score['severity'] in severity_map:
            # Check if the severity indicates a problem (score >= 1)
            if severity_map[score['severity']] >= 1:
                 # Exclude summary scores like 'Average Symptom Score'
                if "Average" not in score['domain']:
                     severity_text = score['severity'].replace("A ", "").replace(" problem", "").capitalize()
                     impacted.append(f"{score['domain']} ({severity_text})")

    # Sort alphabetically for consistency, could also sort by severity later if needed
    impacted.sort()
    return impacted

def get_severe_npq_symptoms(npq_questions, min_severity_score=2):
    """Identifies specific NPQ questions rated as moderate or severe."""
    severe_symptoms = []
    severity_map = {"Not a problem": 0, "A mild problem": 1, "Mild": 1,
                    "A moderate problem": 2, "Moderate": 2,
                    "A severe problem": 3, "Severe": 3}

    for q in npq_questions:
         # Check if 'severity' key exists and has a mappable value
        if q.get('severity') and q['severity'] in severity_map:
             if severity_map[q['severity']] >= min_severity_score:
                severity_text = q['severity'].replace("A ", "").replace(" problem", "").capitalize()
                severe_symptoms.append(f"{q['question_text']} ({severity_text})")

    # Sort alphabetically for consistency
    severe_symptoms.sort()
    return severe_symptoms

# --- Main Script ---

# Load the data
file_path = '40436.json'
with open(file_path, 'r') as f:
    data = json.load(f)

# Basic Info
patient_id = data.get('patient', {}).get('id_number', 'N/A')
test_date = data.get('patient', {}).get('test_completed', 'N/A')

# ADHD Screening Logic
adhd_presentation = None
inattention_met_count = 0
hyperactivity_met_count = 0
adhd_screening_outcome_statement = "ASRS/DSM-5 alignment data not available."
adhd_criteria_details = ""
summary_adhd_screening_outcome = "ASRS/DSM-5 alignment was not assessed or data is missing."
recommendation_focus_adhd = "" # Part of the final recommendation sentence

if data.get('dass_summary') and data.get('dass_items'):
    # Check if a presentation diagnosis exists
    adhd_presentation = data['dass_summary'][0].get('diagnosis')

    # Count met criteria regardless of presentation diagnosis
    for item in data['dass_items']:
        if item.get('is_met') == 1:
            if item['dsm_category'] == 'Inattention':
                inattention_met_count += 1
            elif item['dsm_category'] == 'Hyperactivity/Impulsivity':
                hyperactivity_met_count += 1

    # Determine outcome statement based on presentation AND counts (example threshold: >=5 for adults)
    # DSM-5 requires 5+ for adults (17+) in either category for a presentation.
    # This logic assumes adult criteria for this example. Adjust if needed.
    meets_inattention_criteria = inattention_met_count >= 5
    meets_hyperactivity_criteria = hyperactivity_met_count >= 5

    if adhd_presentation and "Unknown" not in adhd_presentation and (meets_inattention_criteria or meets_hyperactivity_criteria):
         # Clear indication of meeting criteria based on diagnosed presentation
         adhd_screening_outcome_statement = f"Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening suggests a presentation consistent with **{adhd_presentation}**."
         adhd_criteria_details = (f"* Endorsed symptoms met criteria for **{inattention_met_count}/9 Inattention** domains.\n"
                                  f"* Endorsed symptoms met criteria for **{hyperactivity_met_count}/9 Hyperactivity/Impulsivity** domains.")
         summary_adhd_screening_outcome = f"symptom screening was consistent with an **{adhd_presentation}** profile, meeting criteria for {inattention_met_count}/9 inattention and {hyperactivity_met_count}/9 hyperactivity/impulsivity symptoms."
         recommendation_focus_adhd = "confirm the potential ADHD presentation"

    elif meets_inattention_criteria or meets_hyperactivity_criteria:
         # Meets numeric criteria but no specific presentation assigned (or assigned 'Unknown')
         adhd_screening_outcome_statement = "Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening indicates a significant number of endorsed ADHD-related symptoms, but a specific presentation was not determined by this screener."
         adhd_criteria_details = (f"* Endorsed symptoms met criteria for **{inattention_met_count}/9 Inattention** domains.\n"
                                 f"* Endorsed symptoms met criteria for **{hyperactivity_met_count}/9 Hyperactivity/Impulsivity** domains.")
         summary_adhd_screening_outcome = f"symptom screening indicated clinically significant ADHD-related symptoms ({inattention_met_count}/9 inattention, {hyperactivity_met_count}/9 hyperactivity/impulsivity), warranting further investigation."
         recommendation_focus_adhd = "clarify a potential ADHD presentation"
    else:
        # Does not meet numeric criteria
        adhd_screening_outcome_statement = "Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening **did not meet the threshold criteria** for an ADHD presentation."
        # Optionally report endorsed counts even if below threshold
        adhd_criteria_details = (f"* Endorsed symptoms aligned with **{inattention_met_count}/9 Inattention** criteria.\n"
                                 f"* Endorsed symptoms aligned with **{hyperactivity_met_count}/9 Hyperactivity/Impulsivity** criteria.")
        summary_adhd_screening_outcome = f"symptom screening did not meet threshold criteria for an ADHD presentation ({inattention_met_count}/9 inattention, {hyperactivity_met_count}/9 hyperactivity/impulsivity)."
        # No ADHD focus needed unless other things pop up
        recommendation_focus_adhd = ""


# Cognitive Performance
nci_score = "N/A"
nci_percentile = "N/A"
nci_range = "N/A"
list_of_cognitive_strengths = "N/A"
list_of_cognitive_weaknesses = "N/A"
list_of_notable_subtest_scores = "N/A"
summary_cognitive_profile = "Cognitive performance was not assessed or data is missing."

if data.get('cognitive_scores'):
    nci_data = next((item for item in data['cognitive_scores'] if item['domain'] == 'Neurocognition Index (NCI)'), None)
    if nci_data:
        nci_score = nci_data.get('standard_score', 'N/A')
        nci_percentile = nci_data.get('percentile', 'N/A')
        nci_range = get_score_range(nci_percentile)

    strengths, weaknesses = get_cognitive_scores_by_percentile(data['cognitive_scores'])
    list_of_cognitive_strengths = "\n".join([f"* {s}" for s in strengths]) if strengths else "No specific strengths noted (>= 75th percentile)."
    list_of_cognitive_weaknesses = "\n".join([f"* {w}" for w in weaknesses]) if weaknesses else "No specific weaknesses noted (<= 16th percentile)."

    # Create summary statement
    strength_summary = f"strengths in {', '.join([s.split(' (Percentile:')[0] for s in strengths])}" if strengths else "no specific high-performing areas"
    weakness_summary = f"weaknesses in {', '.join([w.split(' (Percentile:')[0] for w in weaknesses])}" if weaknesses else "no specific low-performing areas"
    summary_cognitive_profile = f"overall cognitive performance was in the {nci_range.lower()} range, with {strength_summary.lower()} and relative {weakness_summary.lower()}."


if data.get('subtests'):
    notable_subtests = get_notable_subtest_scores(data['subtests'])
    list_of_notable_subtest_scores = "\n".join([f"* {s}" for s in notable_subtests]) if notable_subtests else "No subtest scores reached notable highs (>= 91st percentile) or lows (<= 9th percentile)."


# NPQ Symptoms
list_of_npq_impacted_domains = "NPQ scores not available."
list_of_severe_npq_symptoms = "NPQ questions not available."
summary_npq_findings = "Self-reported symptoms via NPQ were not assessed or data is missing."
recommendation_focus_npq = "" # Part of final recommendation

if data.get('npq_scores'):
    impacted_domains = get_npq_impacted_domains(data['npq_scores'])
    list_of_npq_impacted_domains = "\n".join([f"* {d}" for d in impacted_domains]) if impacted_domains else "No domains reported with Mild or greater severity."

    # Extract just domain names for summary
    impacted_domain_names = [d.split(' (')[0] for d in impacted_domains]
    if impacted_domain_names:
        summary_npq_findings = f"the NPQ highlighted concerns in areas including {', '.join(impacted_domain_names[:4]).lower()}{'...' if len(impacted_domain_names) > 4 else '.'}"
        # Add NPQ focus to recommendations if significant issues found
        recommendation_focus_npq = f"assess the reported {', '.join(impacted_domain_names[:2]).lower()} symptoms"
    else:
        summary_npq_findings = "the NPQ did not indicate significant concerns in the surveyed domains."


if data.get('npq_questions'):
    severe_symptoms = get_severe_npq_symptoms(data['npq_questions'])
    list_of_severe_npq_symptoms = "\n".join([f"* {s}" for s in severe_symptoms]) if severe_symptoms else "No specific symptoms reported as Moderate or Severe."


# Epworth Sleepiness Scale
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


# Construct Final Recommendation Sentence
rec_parts = [part for part in [recommendation_focus_adhd, recommendation_focus_npq, recommendation_focus_sleep] if part]
if not rec_parts:
     # Default if nothing specific stood out
    recommendation_focus = "further explore the patient's functioning and any reported concerns"
elif len(rec_parts) == 1:
    recommendation_focus = rec_parts[0]
else:
    # Combine multiple focus areas
    recommendation_focus = ", ".join(rec_parts[:-1]) + (" and " if len(rec_parts) > 1 else "") + rec_parts[-1]


# Populate the template
template = """
**Patient ID:** [{patient_id}]
**Test Date:** [{test_date}]

**Referral & Assessment Context:**
This report summarizes the results of a cognitive and symptom screening assessment for Patient ID [{patient_id}], completed on [{test_date}]. **Please note:** This assessment is a screening tool and is **not diagnostic**. Results should be interpreted by a qualified healthcare professional in the context of a full clinical evaluation.

**Symptom Screening Results (ASRS/DSM-5 Alignment):**
{adhd_screening_outcome_statement}
{adhd_criteria_details}

**Cognitive Performance:**
The overall Neurocognition Index (NCI) was in the [{nci_range}] range (Standard Score: [{nci_score}], Percentile: [{nci_percentile}]).
* **Cognitive Strengths:**
{list_of_cognitive_strengths}
* **Cognitive Weaknesses:**
{list_of_cognitive_weaknesses}
* **Specific Subtest Observations:**
{list_of_notable_subtest_scores}

**Self-Reported Symptoms (NPQ):**
The Neuropsychiatric Questionnaire (NPQ) provides further insight into the patient's subjective experience across various domains.
* **Most Impacted Domains (Mild Severity or Higher):**
{list_of_npq_impacted_domains}
* **Most Severe Specific Symptoms Reported (Moderate/Severe):**
{list_of_severe_npq_symptoms}
{optional_epworth_summary}

**Summary & Integration:**
This screening assessment integrated cognitive performance testing and self-reported symptom questionnaires for Patient ID [{patient_id}].

* **Symptom Screening:** {summary_adhd_screening_outcome}
* **Cognitive Profile:** {summary_cognitive_profile}
* **Self-Reported Symptoms (NPQ):** {summary_npq_findings} {summary_sleepiness}

**Recommendations:**
Based on the screening results, further clinical evaluation is recommended. This evaluation should {recommendation_focus}. The information gathered here provides a baseline and highlights areas for more in-depth assessment by a qualified healthcare professional.
"""

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

# print(summary) # For testing - the template and script are the primary outputs here.
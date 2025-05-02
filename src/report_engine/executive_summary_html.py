"""
Direct HTML executive summary generator for Lucid reports.
Refactored to include all logic from executive_summary.py (no Markdown, no template).
"""
from typing import Dict, Any, List
from collections import Counter

# === CONFIGURATION FLAG ===
USE_SCAFFOLD_SUMMARY = True  # Set to False to use the native HTML summary logic

def get_score_range(percentile):
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
    domain = item.get('domain') if score_type == 'cognitive' else f"{item.get('subtest_name', '')} - {item.get('metric', '')}"
    percentile = item.get('percentile')
    is_valid = False
    if score_type == 'cognitive':
        is_valid = item.get('validity_index', '').strip().lower() == 'yes'
    elif score_type == 'subtest':
        is_valid = item.get('validity_flag') == 1
    if not is_valid:
        return None
    if percentile is None: return None
    try:
        p = float(percentile)
        return f"{domain} (Percentile: {p:.1f}, Range: {get_score_range(p)})"
    except (ValueError, TypeError):
        return f"{domain} (Percentile: {percentile}, Range: Error processing)"

def get_cognitive_scores_by_percentile(cognitive_scores, min_percentile=75, max_percentile=16):
    strengths = []
    weaknesses = []
    skip_domains = ["Neurocognition Index (NCI)", "Composite Memory"]
    for score in cognitive_scores:
        if score.get('domain') in skip_domains: continue
        formatted_entry = format_score_entry(score, score_type='cognitive')
        if not formatted_entry: continue
        try:
            percentile_str = formatted_entry.split('Percentile: ')[1].split(',')[0]
            percentile = float(percentile_str)
            if percentile >= min_percentile:
                strengths.append(formatted_entry)
            elif percentile <= max_percentile:
                weaknesses.append(formatted_entry)
        except (ValueError, TypeError, IndexError):
            continue
    strengths.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]), reverse=True)
    weaknesses.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]))
    return strengths, weaknesses

def get_notable_subtest_scores(subtests, min_percentile=91, max_percentile=9):
    notable_scores = []
    for subtest in subtests:
        formatted_entry = format_score_entry(subtest, score_type='subtest')
        if not formatted_entry: continue
        try:
            percentile_str = formatted_entry.split('Percentile: ')[1].split(',')[0]
            percentile = float(percentile_str)
            if percentile >= min_percentile or percentile <= max_percentile:
                notable_scores.append(formatted_entry)
        except (ValueError, TypeError, IndexError):
            continue
    notable_scores.sort(key=lambda x: float(x.split('Percentile: ')[1].split(',')[0]))
    return notable_scores

def get_npq_impacted_domains(npq_scores, min_severity_level=2):
    impacted = []
    severity_map = {"Not a problem": 0, "A mild problem": 1, "Mild": 1,
                    "A moderate problem": 2, "Moderate": 2,
                    "A severe problem": 3, "Severe": 3}
    for score in npq_scores:
        if score.get('severity') and score['severity'] in severity_map:
            current_severity_level = severity_map[score['severity']]
            if current_severity_level >= min_severity_level:
                if "Average" not in score['domain']:
                    severity_text = score['severity'].replace("A ", "").replace(" problem", "").capitalize()
                    impacted.append(f"{score['domain']} ({severity_text})")
    impacted.sort()
    return impacted

def get_severe_npq_symptoms(npq_questions, min_severity_score=2):
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
    severe.sort()
    moderate.sort()
    return severe + moderate

def format_cognitive_score(score_item):
    if score_item.get('validity_index', '').strip().lower() != 'yes':
        return f"{score_item.get('domain', 'Unknown Domain')} (Invalid)"
    percentile = score_item.get('percentile')
    domain = score_item.get('domain', 'Unknown Domain')
    if percentile is None: return f"{domain} (Percentile: N/A)"
    try:
        p = float(percentile)
        return f"{domain} (Percentile: {p:.1f}, Range: {get_score_range(p)})"
    except (ValueError, TypeError):
        return f"{domain} (Percentile: {percentile}, Range: Error processing)"

def format_subtest_score(subtest_item):
    if subtest_item.get('validity_flag') != 1:
        return f"{subtest_item.get('subtest_name', 'Unknown')}-{subtest_item.get('metric','Metric')} (Invalid)"
    percentile = subtest_item.get('percentile')
    name = f"{subtest_item.get('subtest_name', 'Unknown')}-{subtest_item.get('metric','Metric')}"
    if percentile is None: return f"{name} (Percentile: N/A)"
    try:
        p = float(percentile)
        return f"{name} (Percentile: {p:.1f}, Range: {get_score_range(p)})"
    except (ValueError, TypeError):
        return f"{name} (Percentile: {percentile}, Range: Error processing)"

def get_met_dsm_criteria(dass_items, category):
    met_criteria = []
    if dass_items:
        for item in dass_items:
            if item.get('dsm_category') == category and item.get('is_met') == 1:
                desc = item.get('dsm_criterion', 'Unknown Criterion').split(': ')[-1]
                met_criteria.append(desc)
    return met_criteria

def get_npq_symptoms(npq_questions, domain, min_severity_score=2):
    symptoms = []
    severity_map = {"Not a problem": 0, "A mild problem": 1, "Mild": 1,
                    "A moderate problem": 2, "Moderate": 2,
                    "A severe problem": 3, "Severe": 3}
    if npq_questions:
        for q in npq_questions:
            if q.get('domain') == domain:
                severity_text = q.get('severity')
                if severity_text and severity_text in severity_map:
                    if severity_map[severity_text] >= min_severity_score:
                        severity_label = severity_text.replace("A ", "").replace(" problem", "").capitalize()
                        question_text = q.get('question_text', 'Unknown question')
                        symptoms.append(f'"{question_text}" ({severity_label})')
    return symptoms

def get_npq_domain_severity(npq_scores, domain_name):
    if npq_scores:
        for score in npq_scores:
            if score.get('domain') == domain_name:
                sev = score.get('severity', "Not rated")
                return sev.replace("A ", "").replace(" problem", "").capitalize()
    return "Not rated"

def get_asrs_response(asrs_items, question_number):
    if asrs_items:
        for item in asrs_items:
            if item.get('question_number') == question_number:
                return item.get('response', 'N/A')
    return 'N/A'

def generate_structured_adhd_summary_html(data):
    """
    Generate a structured, clinically relevant ADHD/Executive summary in HTML.
    """
    patient_id = data.get('patient', {}).get('id_number', 'N/A')
    dass_summary = data.get('dass_summary', [])
    dass_items = data.get('dass_items', [])
    npq_questions = data.get('npq_questions', [])
    npq_scores = data.get('npq_scores', [])
    cognitive_scores = data.get('cognitive_scores', [])
    subtests = data.get('subtests', [])
    asrs = data.get('asrs', [])

    html = []
    html.append(f'<div class="adhd-structured-summary"><h2>Structured ADHD & Executive Function Summary <span style="font-size:0.8em; color:#64748b;">(Patient {patient_id})</span></h2>')
    overall_presentation = dass_summary[0].get('diagnosis', 'Unknown') if dass_summary else 'Unknown'
    inattention_met_count = sum(1 for item in dass_items if item.get('dsm_category') == 'Inattention' and item.get('is_met') == 1)
    hyperactivity_met_count = sum(1 for item in dass_items if item.get('dsm_category') == 'Hyperactivity/Impulsivity' and item.get('is_met') == 1)
    html.append(f'<div class="adhd-criteria-row"><b>DSM-5 Symptom Endorsement (Self-Report via ASRS Alignment):</b>')
    html.append(f'<ul><li><b>Overall:</b> {overall_presentation}</li><li><b>Inattention:</b> {inattention_met_count}/9 criteria met</li><li><b>Hyperactivity/Impulsivity:</b> {hyperactivity_met_count}/9 criteria met</li></ul></div>')
    html.append('<hr style="margin:0.5em 0;">')
    html.append('<div class="adhd-domain-section"><b>Domain-Specific Findings</b>')

    # 1. Attention Domain
    html.append('<div class="adhd-domain"><b>1. Attention</b><ul>')
    met_inattention_dsm = get_met_dsm_criteria(dass_items, 'Inattention')
    if met_inattention_dsm:
        html.append(f'<li><b>DSM:</b> Meets {len(met_inattention_dsm)}/9 criteria: ' + ", ".join(met_inattention_dsm[:4]) + ('...' if len(met_inattention_dsm)>4 else '') + '</li>')
    else:
        html.append('<li><b>DSM:</b> No Inattention criteria met.</li>')
    npq_attention_mod_sev = get_npq_symptoms(npq_questions, 'Attention', 2)
    if npq_attention_mod_sev:
        html.append(f'<li><b>NPQ (Moderate/Severe):</b> ' + ", ".join(npq_attention_mod_sev[:4]) + ('...' if len(npq_attention_mod_sev)>4 else '') + '</li>')
    else:
        html.append('<li><b>NPQ (Moderate/Severe):</b> No moderate or severe attention symptoms reported.</li>')
    cognitive_attention = [formatted for score in cognitive_scores if score.get('domain') in ['Simple Attention', 'Complex Attention*', 'Sustained Attention'] and (formatted := format_cognitive_score(score)) and 'Invalid' not in formatted]
    if cognitive_attention:
        for score in sorted(cognitive_attention): html.append(f'<li><b>Cognitive:</b> {score}</li>')
    else:
        html.append('<li><b>Cognitive:</b> Relevant domain scores not available or invalid.</li>')
    html.append('</ul></div>')

    # 2. Executive Function Domain
    html.append('<div class="adhd-domain"><b>2. Executive Function</b><ul>')
    ef_overall_formatted = next((formatted for score in cognitive_scores if score.get('domain') == 'Executive Function' and (formatted := format_cognitive_score(score))), None)
    if ef_overall_formatted and 'Invalid' not in ef_overall_formatted:
        html.append(f'<li><b>Overall Cognitive:</b> {ef_overall_formatted}</li>')
    else:
        html.append(f'<li><b>Overall Cognitive:</b> {ef_overall_formatted or "Not Available"}</li>')
    html.append('</ul></div>')

    # 3. Memory Domain
    html.append('<div class="adhd-domain"><b>3. Memory</b><ul>')
    cog_mem_formatted = [formatted for s in cognitive_scores if 'Memory' in s.get('domain','') and (formatted := format_cognitive_score(s)) and 'Invalid' not in formatted]
    if cog_mem_formatted:
        for score in sorted(cog_mem_formatted): html.append(f'<li><b>Cognitive:</b> {score}</li>')
    else:
        html.append('<li><b>Cognitive:</b> Relevant domain scores not available or invalid.</li>')
    html.append('</ul></div>')

    # 4. Impulsivity Domain (optional, can expand if needed)
    html.append('<div class="adhd-domain"><b>4. Impulsivity</b><ul>')
    met_impulsive_dsm = [item.get('dsm_criterion').split(': ')[-1] for item in dass_items if item.get('dsm_category') == 'Hyperactivity/Impulsivity' and item.get('is_met') == 1 and item.get('dsm_criterion','').startswith(('B7:','B9:'))]
    if met_impulsive_dsm:
        html.append(f'<li><b>DSM:</b> ' + ", ".join(met_impulsive_dsm[:4]) + ('...' if len(met_impulsive_dsm)>4 else '') + '</li>')
    else:
        html.append('<li><b>DSM:</b> No impulsivity criteria met.</li>')
    html.append('</ul></div>')

    html.append('</div></div>')
    return "\n".join(html)

def get_executive_summary_section(data):
    import importlib.util
    import os
    import markdown

    if USE_SCAFFOLD_SUMMARY:
        # Dynamically import the scaffold summary function
        scaffold_path = os.path.join(os.path.dirname(__file__), 'scaffold_executive_summary.py')
        spec = importlib.util.spec_from_file_location('scaffold_executive_summary', scaffold_path)
        scaffold_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scaffold_mod)
        # Call the function and convert Markdown to HTML for proper rendering and pagination
        summary_md = scaffold_mod.generate_adhd_summary(data)
        summary_html = markdown.markdown(summary_md)
        # Add heading and wrap in a styled div for font size and readability
        return (
            '<div class="executive-summary" style="font-size: 1.13em; line-height:1.6; margin-bottom:1.5em;">'
            '<h2 style="margin-top:0;margin-bottom:0.7em;font-size:1.35em; color:#1e293b;">Assessment Summary</h2>'
            f'{summary_html}'
            '</div>'
        )
    else:
        return generate_structured_adhd_summary_html(data)

def generate_cognitive_profile_summary_html(data: Dict[str, Any]) -> str:
    """
    Generate the cognitive profile executive summary as modern HTML from JSON data.
    Replicates all logic from executive_summary.py and replaces the Markdown/template approach.
    """
    # --- Styles ---
    style = '''<style>
    .executive-summary {
        background: #f8fafc;
        border-radius: 1.2rem;
        box-shadow: 0 2px 8px rgba(37,99,235,0.06);
        padding: 2.2rem 2.2rem 1.7rem 2.2rem;
        border: 1.5px solid #e0e7ef;
        margin-bottom: 2.5em;
        font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif;
        font-size: 1.14em;
        line-height: 1.7;
        color: #1e293b;
    }
    .executive-summary h2, .exec-summary-section h2 {
        color: #1e3a8a;
        font-size: 1.45em;
        font-weight: 700;
        margin-top: 0;
        margin-bottom: 1.1em;
        letter-spacing: 0.01em;
    }
    .executive-summary h3, .exec-summary-section h3 {
        color: #2563eb;
        font-size: 1.12em;
        font-weight: 600;
        margin-top: 1.1em;
        margin-bottom: 0.4em;
    }
    .executive-summary ul, .exec-summary-section ul {
        margin-left: 1.6em;
        margin-bottom: 1.2em;
    }
    .executive-summary li, .exec-summary-section li {
        margin-bottom: 0.45em;
        font-size: 1em;
    }
    .exec-summary-key {
        color: #2563eb;
        font-weight: 600;
    }
    .exec-summary-note {
        background: #e0e7ef;
        color: #334155;
        border-radius: 0.5em;
        padding: 0.7em 1em;
        margin-bottom: 1.5em;
        display: block;
        font-size: 0.99em;
    }
    .highlight {
        background: #dbeafe;
        color: #1e3a8a;
        padding: 0.1em 0.35em;
        border-radius: 0.3em;
        font-weight: 600;
    }
    </style>'''
    # --- Basic Info ---
    patient_id = data.get('patient', {}).get('id_number', 'N/A')
    test_date = data.get('patient', {}).get('test_completed', 'N/A')

    # --- ADHD Screening Logic ---
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
            adhd_screening_outcome_statement = f"Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening suggests a presentation consistent with {adhd_presentation}."
            adhd_criteria_details = (f"* Endorsed symptoms met criteria for {inattention_met_count}/9 Inattention domains.\n"
                                    f"* Endorsed symptoms met criteria for {hyperactivity_met_count}/9 Hyperactivity/Impulsivity domains.")
            summary_adhd_screening_outcome = f"symptom screening was consistent with an {adhd_presentation} profile, meeting criteria for {inattention_met_count}/9 inattention and {hyperactivity_met_count}/9 hyperactivity/impulsivity symptoms."
            recommendation_focus_adhd = "confirm the potential ADHD presentation"
        elif meets_inattention_criteria or meets_hyperactivity_criteria:
            adhd_screening_outcome_statement = "Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening indicates a significant number of endorsed ADHD-related symptoms, but a specific presentation was not determined by this screener."
            adhd_criteria_details = (f"* Endorsed symptoms met criteria for {inattention_met_count}/9 Inattention domains.\n"
                                    f"* Endorsed symptoms met criteria for {hyperactivity_met_count}/9 Hyperactivity/Impulsivity domains.")
            summary_adhd_screening_outcome = f"symptom screening indicated clinically significant ADHD-related symptoms ({inattention_met_count}/9 inattention, {hyperactivity_met_count}/9 hyperactivity/impulsivity), warranting further investigation."
            recommendation_focus_adhd = "clarify a potential ADHD presentation"
        else:
            adhd_screening_outcome_statement = "Based on self-reported symptoms (ASRS/DSM-5 alignment), the screening did not meet the threshold criteria for an ADHD presentation."
            adhd_criteria_details = (f"* Endorsed symptoms aligned with {inattention_met_count}/9 Inattention criteria.\n"
                                    f"* Endorsed symptoms aligned with {hyperactivity_met_count}/9 Hyperactivity/Impulsivity criteria.")
            summary_adhd_screening_outcome = f"symptom screening did not meet threshold criteria for an ADHD presentation ({inattention_met_count}/9 inattention, {hyperactivity_met_count}/9 hyperactivity/impulsivity)."
            recommendation_focus_adhd = ""
    # ADHD Criteria Details (HTML list)
    criteria_details = adhd_criteria_details
    if criteria_details:
        adhd_criteria_details_html = '<ul class="adhd-criteria-list">' + ''.join(f'<li>{line[2:]}</li>' for line in criteria_details.splitlines() if line.startswith('* ')) + '</ul>'
    else:
        adhd_criteria_details_html = ''

    # --- Cognitive Performance ---
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
            nci_valid = nci_data.get('validity_index', '').strip().lower() == 'yes'
            if nci_valid:
                nci_score = nci_data.get('standard_score', 'N/A')
                nci_percentile = nci_data.get('percentile', 'N/A')
                nci_range = get_score_range(nci_percentile)
            else:
                nci_range = nci_score = nci_percentile = "Invalid"
        strengths, weaknesses = get_cognitive_scores_by_percentile(data['cognitive_scores'])
        list_of_cognitive_strengths = '<ul>' + ''.join(f'<li>{s}</li>' for s in strengths) + '</ul>' if strengths else "No specific <em>valid</em> strengths noted (>= 75th percentile)."
        list_of_cognitive_weaknesses = '<ul>' + ''.join(f'<li>{w}</li>' for w in weaknesses) + '</ul>' if weaknesses else "No specific <em>valid</em> weaknesses noted (<= 16th percentile)."
        if nci_range != "Invalid":
            strength_summary = f"strengths in {', '.join([s.split(' (Percentile:')[0] for s in strengths])}" if strengths else "no specific high-performing areas"
            weakness_summary = f"weaknesses in {', '.join([w.split(' (Percentile:')[0] for w in weaknesses])}" if weaknesses else "no specific low-performing areas"
            summary_cognitive_profile = f"overall <em>valid</em> cognitive performance (NCI) was in the {nci_range.lower()} range, with {strength_summary.lower()} and relative {weakness_summary.lower()} noted in valid domains."
        else:
            summary_cognitive_profile = "the overall cognitive index (NCI) was invalid. Analysis focused on individual valid domains."
            if strengths or weaknesses:
                strength_summary = f"valid strengths in {', '.join([s.split(' (Percentile:')[0] for s in strengths])}" if strengths else "no specific high-performing areas"
                weakness_summary = f"valid weaknesses in {', '.join([w.split(' (Percentile:')[0] for w in weaknesses])}" if weaknesses else "no specific low-performing areas"
                summary_cognitive_profile += f" Within validly assessed domains, {strength_summary.lower()} and relative {weakness_summary.lower()} were observed."
    if data.get('subtests'):
        notable_subtests = get_notable_subtest_scores(data['subtests'])
        list_of_notable_subtest_scores = '<ul>' + ''.join(f'<li>{s}</li>' for s in notable_subtests) + '</ul>' if notable_subtests else "No <em>valid</em> subtest scores reached notable highs (>= 91st percentile) or lows (<= 9th percentile)."
    else:
        list_of_notable_subtest_scores = "Subtest data not available."

    # --- NPQ Symptoms ---
    list_of_npq_impacted_domains = "NPQ scores not available."
    list_of_severe_npq_symptoms = "NPQ questions not available."
    summary_npq_findings = "Self-reported symptoms via NPQ were not assessed or data is missing."
    recommendation_focus_npq = ""
    if data.get('npq_scores'):
        impacted_domains = get_npq_impacted_domains(data['npq_scores'], min_severity_level=2)
        list_of_npq_impacted_domains = '<ul>' + ''.join(f'<li>{d}</li>' for d in impacted_domains) + '</ul>' if impacted_domains else "No domains reported with Moderate or greater severity."
        impacted_domain_names = [d.split(' (')[0] for d in impacted_domains]
        if impacted_domain_names:
            summary_npq_findings = f"the NPQ highlighted concerns rated <strong>Moderate or Severe</strong> in areas including {', '.join(impacted_domain_names).lower()}."
            recommendation_focus_npq = f"assess the reported moderate/severe {', '.join(impacted_domain_names[:2]).lower()} symptoms"
        else:
            summary_npq_findings = "the NPQ did not indicate significant concerns rated Moderate or Severe in the surveyed domains."
    if data.get('npq_questions'):
        severe_symptoms = get_severe_npq_symptoms(data['npq_questions'], min_severity_score=2)
        list_of_severe_npq_symptoms = '<ul>' + ''.join(f'<li>{s}</li>' for s in severe_symptoms) + '</ul>' if severe_symptoms else "No specific symptoms reported as Moderate or Severe."
    else:
        list_of_severe_npq_symptoms = "NPQ detailed responses not available."

    # --- Epworth Sleepiness Scale ---
    optional_epworth_summary = ""
    summary_sleepiness = ""
    recommendation_focus_sleep = ""
    if data.get('epworth') and data['epworth'].get('summary'):
        epworth_summary_data = data['epworth']['summary'][0]
        epworth_score = epworth_summary_data.get('total_score')
        epworth_interpretation = epworth_summary_data.get('interpretation', '').strip('.')
        if epworth_score is not None and epworth_interpretation:
            optional_epworth_summary = f"The Epworth Sleepiness Scale indicated <strong>{epworth_interpretation}</strong> (Total Score: {epworth_score})."
            if "moderate" in epworth_interpretation.lower() or "excessive" in epworth_interpretation.lower() or "severe" in epworth_interpretation.lower():
                summary_sleepiness = f"Potential {epworth_interpretation.lower()} was also noted."
                recommendation_focus_sleep = "evaluate potential sleep-related issues"
    # --- Final Recommendation Sentence ---
    rec_parts = [part for part in [recommendation_focus_adhd, recommendation_focus_npq, recommendation_focus_sleep] if part]
    if not rec_parts:
        recommendation_focus = "further explore the patient's functioning and any reported concerns"
    elif len(rec_parts) == 1:
        recommendation_focus = rec_parts[0]
    else:
        recommendation_focus = ", ".join(rec_parts[:-1]) + (" and " if len(rec_parts) > 1 else "") + rec_parts[-1]

    # --- HTML Output ---
    note = '<div class="exec-summary-note" style="font-size:10px;color:#dc2626;margin-bottom:0.8em;">'
    note += 'This automatically generated report is not a substitute for clinical judgement. '
    note += 'Results should be interpreted by a qualified healthcare professional in the context of a full clinical evaluation. '
    note += 'Invalid test results have been excluded from interpretation below.'
    note += '</div>'
    html = f'''{style}<div class="executive-summary">
    {note}
    <section class="exec-summary-section"><h2>1. Symptom Screening Results (ASRS/DSM-5 Alignment)</h2>
        {get_executive_summary_section(data)}
    </section>
    <section class="exec-summary-section"><h2>2. Cognitive Performance</h2>
        <div><span class="exec-summary-key">Neurocognition Index (NCI):</span> Range: <strong>{nci_range}</strong> | Standard Score: <strong>{nci_score}</strong> | Percentile: <strong>{nci_percentile}</strong></div>
        <h3>2.1 Cognitive Strengths</h3>{list_of_cognitive_strengths}
        <h3>2.2 Cognitive Weaknesses</h3>{list_of_cognitive_weaknesses}
        <h3>2.3 Specific Subtest Observations</h3>{list_of_notable_subtest_scores}
    </section>
    <section class="exec-summary-section"><h2>3. Self-Reported Symptoms (NPQ)</h2>
        <div>The Neuropsychiatric Questionnaire (NPQ) provides insight into the patient's subjective experience. This summary focuses on areas rated as <strong>Moderate or Severe</strong>.</div>
        <div><span class="exec-summary-key">Most Impacted Domains (Moderate Severity or Higher):</span></div>
        {list_of_npq_impacted_domains}
        <div><span class="exec-summary-key">Specific Symptoms Reported as Moderate or Severe:</span></div>
        {list_of_severe_npq_symptoms}
        <div>{optional_epworth_summary}</div>
    </section>
    <section class="exec-summary-section"><h2>4. Summary & Integration</h2>
        <div>This screening assessment integrated cognitive performance testing (reporting only on valid results) and self-reported symptom questionnaires for Patient ID <strong>{patient_id}</strong>.<br>
        <ul>
            <li><strong>Symptom Screening:</strong> {summary_adhd_screening_outcome}</li>
            <li><strong>Cognitive Profile:</strong> {summary_cognitive_profile}</li>
            <li><strong>Self-Reported Symptoms (NPQ):</strong> {summary_npq_findings} {summary_sleepiness}</li>
        </ul>
        </div>
        <div><span class="exec-summary-key">Recommendations</span></div>
        <div>Based on the screening results, further clinical evaluation is recommended. This evaluation should <span class="highlight">{recommendation_focus}</span>.<br>
        The information gathered here provides a baseline and highlights areas for more in-depth assessment by a qualified healthcare professional.</div>
    </section>
    </div>'''
    return html

# --- TESTING HOOK: Only runs if __name__ == "__main__" ---
if __name__ == "__main__":
    import json
    import os
    test_json_path = r"G:\My Drive\Programming\Lucid the App\Project Folder\src\json\40436.json"
    output_html_path = r"G:\My Drive\Programming\Lucid the App\Project Folder\src\json\40436_executive_summary.html"
    if os.path.exists(test_json_path):
        with open(test_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        html = generate_cognitive_profile_summary_html(data)
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Executive summary HTML generated: {output_html_path}")
    else:
        print(f"Test JSON file not found: {test_json_path}")

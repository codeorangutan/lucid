import json

# --- Helper Functions ---

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

def format_cognitive_score(score_item):
    """Formats a single cognitive score entry if valid."""
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
    """Formats a single subtest score entry if valid."""
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
    """Gets a list of met DSM criteria descriptions for a category."""
    met_criteria = []
    if dass_items:
        for item in dass_items:
            if item.get('dsm_category') == category and item.get('is_met') == 1:
                # Extract the description part
                desc = item.get('dsm_criterion', 'Unknown Criterion').split(': ')[-1]
                met_criteria.append(desc)
    return met_criteria

def get_npq_symptoms(npq_questions, domain, min_severity_score=2):
    """Gets NPQ symptoms for a domain meeting minimum severity."""
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
                         symptoms.append(f"\"{q.get('question_text', 'Unknown question')}\" ({severity_label})")
    return symptoms

def get_npq_domain_severity(npq_scores, domain_name):
     """Gets the overall severity rating for a specific NPQ domain."""
     if npq_scores:
         for score in npq_scores:
             if score.get('domain') == domain_name:
                 sev = score.get('severity', "Not rated")
                 return sev.replace("A ", "").replace(" problem", "").capitalize()
     return "Not rated"

def get_asrs_response(asrs_items, question_number):
    """Gets the response for a specific ASRS question number."""
    if asrs_items:
        for item in asrs_items:
            if item.get('question_number') == question_number:
                return item.get('response', 'N/A')
    return 'N/A'

def generate_adhd_summary(data):
    # Extract relevant sections
    patient_id = data.get('patient', {}).get('id_number', 'N/A')
    dass_summary = data.get('dass_summary', [])
    dass_items = data.get('dass_items', [])
    npq_questions = data.get('npq_questions', [])
    npq_scores = data.get('npq_scores', [])
    cognitive_scores = data.get('cognitive_scores', [])
    subtests = data.get('subtests', [])
    asrs = data.get('asrs', [])
    epworth = data.get('epworth', {}).get('summary', [])

    html = []
    html.append('<div class="executive-summary">')
    html.append('<div class="disclaimer" style="font-size:11px;color:#64748b;margin-bottom:0.8em;"><b>Disclaimer:</b> This is an automatically generated summary and is not a substitute for clinical judgement. Results should be interpreted by a qualified healthcare professional in the context of a full clinical evaluation. Invalid test results have been excluded from interpretation below.</div>')
    overall_presentation = dass_summary[0].get('diagnosis', 'Unknown') if dass_summary else 'Unknown'
    inattention_met_count = sum(1 for item in dass_items if item.get('dsm_category') == 'Inattention' and item.get('is_met') == 1)
    hyperactivity_met_count = sum(1 for item in dass_items if item.get('dsm_category') == 'Hyperactivity/Impulsivity' and item.get('is_met') == 1)
    html.append('<h4>DSM-5 Symptom Endorsement (Self-Report via ASRS Alignment):</h4>')
    html.append('<ul>')
    html.append(f'<li><b>Overall:</b> Meets criteria for <b>{overall_presentation}</b>.</li>')
    html.append(f'<li><b>Inattention:</b> {inattention_met_count}/9 criteria met.</li>')
    html.append(f'<li><b>Hyperactivity/Impulsivity:</b> {hyperactivity_met_count}/9 criteria met.</li>')
    html.append('</ul>')
    html.append('<hr>')
    html.append('<h4>Domain-Specific Findings:</h4>')
    html.append('<b>1. Attention:</b>')
    html.append('<ul>')
    met_inattention_dsm = get_met_dsm_criteria(dass_items, 'Inattention')
    if met_inattention_dsm:
        joined = ', '.join(met_inattention_dsm[:3]) + ('...' if len(met_inattention_dsm) > 3 else '')
        html.append(f'<li><b>DSM:</b> Meets all 9 criteria for Inattention (e.g., {joined}).</li>')
    else:
        html.append('<li><b>DSM:</b> No Inattention criteria met.</li>')
    npq_attention_mod_sev = get_npq_symptoms(npq_questions, 'Attention', min_severity_score=2)
    npq_attention_severe = get_npq_symptoms(npq_questions, 'Attention', min_severity_score=3)
    if npq_attention_mod_sev:
        mod_sev_text = ", ".join(npq_attention_mod_sev)
        severe_text = f' The most severe endorsed symptom was {npq_attention_severe[0]}.' if npq_attention_severe else ''
        html.append(f'<li><b>NPQ (Moderate/Severe Symptoms):</b> Reports {mod_sev_text}{severe_text}</li>')
    else:
        html.append('<li><b>NPQ (Moderate/Severe Symptoms):</b> No moderate or severe attention symptoms reported.</li>')
    html.append('</ul>')

    # 2. Executive Function Domain (detailed breakdown)
    html.append('<b>2. Executive Function</b>')
    html.append('<ul>')
    ef_overall = next((format_cognitive_score(s) for s in cognitive_scores if s.get('domain') == 'Executive Function'), None)
    if ef_overall and 'Invalid' not in ef_overall:
        html.append(f'<li><b>Overall Cognitive Score (Valid):</b> {ef_overall.split("(")[-1].split(")")[0]}.</li>')
    else:
        html.append(f'<li><b>Overall Cognitive Score (Valid):</b> {ef_overall or "Not Available"}.</li>')

    # Planning & Organization
    html.append('<li><b>Planning & Organization:</b><ul>')
    dsm_a5 = any(item.get('dsm_criterion', '').startswith('A5:') and item.get('is_met') == 1 for item in dass_items)
    if dsm_a5:
        html.append('<li>DSM: Endorses "Often has difficulty organizing tasks and activities".</li>')
    npq_plan_org = get_npq_symptoms(npq_questions, 'Attention', 2)
    plan_org_relevant_npq = [s for s in npq_plan_org if 'scattered' in s or 'Organizing' in s]
    if plan_org_relevant_npq:
        html.append(f'<li>NPQ: Reports {", ".join(plan_org_relevant_npq)}.</li>')
    cog_reasoning = next((format_cognitive_score(s) for s in cognitive_scores if s.get('domain') == 'Reasoning'), None)
    if cog_reasoning and 'Invalid' not in cog_reasoning:
        html.append(f'<li>Cognitive: Reasoning score was {cog_reasoning.split("(")[-1].split(")")[0]}.</li>')
    html.append('</ul></li>')

    # Prioritization & Time Management
    html.append('<li><b>Prioritization & Time Management:</b><ul>')
    dsm_a5_a6 = any(item.get('dsm_criterion', '').startswith(('A5:', 'A6:')) and item.get('is_met') == 1 for item in dass_items)
    npq_finish_task = any('Not finishing chores' in s for s in get_npq_symptoms(npq_questions, 'Attention', 3))
    if dsm_a5_a6 or npq_finish_task:
        html.append('<li>DSM/NPQ: Implied by difficulties organizing (A5), avoiding tasks (A6), and severe difficulty finishing projects/chores (NPQ Attention Q9).</li>')
    else:
        html.append('<li>DSM/NPQ: No direct indicators met threshold.</li>')
    html.append('</ul></li>')

    # Task Initiation & Completion
    html.append('<li><b>Task Initiation & Completion:</b><ul>')
    dsm_a4_a6 = [item.get('dsm_criterion').split(': ')[-1] for item in dass_items if item.get('dsm_criterion','').startswith(('A4:','A6:')) and item.get('is_met')==1]
    if dsm_a4_a6:
        joined = ' and '.join(dsm_a4_a6)
        html.append(f'<li>DSM: Endorses "{joined}".</li>')
    npq_finish_task_severe = get_npq_symptoms(npq_questions, 'Attention', 3)
    if npq_finish_task_severe and 'Not finishing chores' in npq_finish_task_severe[0]:
        html.append(f'<li>NPQ: Reports {npq_finish_task_severe[0]}.</li>')
    html.append('</ul></li>')

    # Working Memory
    html.append('<li><b>Working Memory:</b><ul>')
    wm_cog = next((format_cognitive_score(s) for s in cognitive_scores if s.get('domain') == 'Working Memory'), None)
    if wm_cog and 'Invalid' not in wm_cog:
        html.append(f'<li>Cognitive: {wm_cog.split("Range: ")[-1].split(")")[0]} noted ({wm_cog.split(" (")[0]}).</li>')
    else:
        html.append(f'<li>Cognitive: {wm_cog or "Not Available"}.</li>')
    npq_wm_mod = get_npq_symptoms(npq_questions, 'Memory', 2)
    npq_wm_mild = get_npq_symptoms(npq_questions, 'Attention', 1)
    if npq_wm_mod:
        html.append(f'<li>NPQ: Moderate problems with memory including {", ".join(npq_wm_mod[:3])}.</li>')
    if any("Forgetful" in s for s in npq_wm_mild):
        html.append('<li>NPQ: Reports being "Forgetful, I need constant reminding" (Mild).</li>')
    html.append('</ul></li>')

    # Inhibition (Response Control)
    html.append('<li><b>Inhibition (Response Control):</b><ul>')
    dsm_b7_b9 = [item.get('dsm_criterion').split(': ')[-1] for item in dass_items if item.get('dsm_criterion','').startswith(('B7:','B9:')) and item.get('is_met')==1]
    if dsm_b7_b9:
        joined = ' and '.join(dsm_b7_b9)
        html.append(f'<li>DSM: Endorses "{joined}".</li>')
    npq_inhibit = get_npq_symptoms(npq_questions, 'Impulsive', 1)
    if any("Impulsive, act without thinking" in s for s in npq_inhibit):
        html.append('<li>NPQ: Reports being "Impulsive, act without thinking" (Mild).</li>')
    cog_inhibit_errors = [format_subtest_score(st) for st in subtests if 'Commission Errors' in st.get('metric', '') and 'Invalid' not in format_subtest_score(st)]
    if cog_inhibit_errors:
         weak_errors = [s for s in cog_inhibit_errors if 'Impaired' in s or 'Borderline' in s]
         other_errors = [s for s in cog_inhibit_errors if s not in weak_errors]
         if weak_errors:
             html.append(f'<li>Cognitive (Subtests): Significant weaknesses in commission errors (poor inhibition) on { " and ".join([s.split(" (Percentile:")[0] for s in weak_errors]) } ({ "; ".join([s.split("Range: ")[-1] for s in weak_errors]) }).</li>')
         if other_errors:
             html.append(f'<li>Cognitive (Subtests): Other commission errors: { "; ".join([s.split(" (Percentile:")[0] + " (" + s.split("Range: ")[-1] for s in other_errors]) }.</li>')
    else:
        html.append('<li>Cognitive (Subtests): Commission error data not available or invalid.</li>')
    html.append('</ul></li>')

    # Cognitive Flexibility
    html.append('<li><b>Cognitive Flexibility:</b><ul>')
    cog_flex = next((format_cognitive_score(s) for s in cognitive_scores if s.get('domain') == 'Cognitive Flexibility'), None)
    if cog_flex and 'Invalid' not in cog_flex:
        html.append(f'<li>Cognitive: {cog_flex.split("Range: ")[-1].split(")")[0]} performance ({cog_flex.split(" (")[0]}).</li>')
    else:
        html.append(f'<li>Cognitive: {cog_flex or "Not Available"}.</li>')
    sat_scores = [format_subtest_score(st) for st in subtests if st.get('subtest_name') == 'Shifting Attention Test (SAT)' and 'Invalid' not in format_subtest_score(st) and ('Reaction Time' in st.get('metric','') or 'Correct Responses' in st.get('metric',''))]
    if sat_scores:
        html.append(f'<li>Subtests (SAT): { "; ".join([s.split(" (Percentile:")[0] + " (" + s.split("Range: ")[-1] for s in sat_scores]) }.</li>')
    html.append('</ul></li>')

    # Emotional Regulation
    html.append('<li><b>Emotional Regulation:</b><ul>')
    npq_mood_domain = get_npq_domain_severity(npq_scores, "Mood Stability")
    npq_mood_mild = get_npq_symptoms(npq_questions, "Mood Stability", 1)
    npq_anxiety_domain = get_npq_domain_severity(npq_scores, "Anxiety")
    npq_anxiety_mod = get_npq_symptoms(npq_questions, "Anxiety", 2)
    npq_dep_domain = get_npq_domain_severity(npq_scores, "Depression")
    npq_dep_mod = get_npq_symptoms(npq_questions, "Depression", 2)
    npq_oc_mod = get_npq_symptoms(npq_questions, "Obsessions & Compulsions", 2)
    html.append(f'<li>NPQ: Mood Stability domain rated "{npq_mood_domain}"; {", ".join(npq_mood_mild)}. Anxiety domain rated "{npq_anxiety_domain}"; {", ".join(npq_anxiety_mod)}. Depression domain rated "{npq_dep_domain}"; {", ".join(npq_dep_mod)}. OC: {", ".join(npq_oc_mod)}.</li>')
    html.append('</ul></li>')

    html.append('</ul>')

    # 3. Memory Domain
    html.append('<b>3. Memory:</b>')
    html.append('<ul>')
    mem_overall = next((format_cognitive_score(s) for s in cognitive_scores if s.get('domain') == 'Memory'), None)
    if mem_overall and 'Invalid' not in mem_overall:
        html.append(f'<li><b>Overall Cognitive Score (Valid):</b> {mem_overall.split("(")[-1].split(")")[0]}.</li>')
    else:
        html.append(f'<li><b>Overall Cognitive Score (Valid):</b> {mem_overall or "Not Available"}.</li>')
    dsm_a4 = any(item.get('dsm_criterion', '').startswith('A4:') and item.get('is_met') == 1 for item in dass_items)
    if dsm_a4: html.append('<li>DSM: Endorses "Often loses things necessary for tasks or activities".</li>')
    npq_memory_mod = get_npq_symptoms(npq_questions, 'Memory', 2)
    if npq_memory_mod: html.append(f'<li>NPQ (Memory Domain): {", ".join(npq_memory_mod)}</li>')
    mem_subtests = [format_subtest_score(st) for st in subtests if st.get('domain') == 'Memory' and st.get('validity_flag') == 1]
    if mem_subtests: html.append(f'<li>Subtests (Valid): {", ".join(mem_subtests)}.</li>')
    html.append('</ul>')

    # 4. Hyperactivity / Motor Domain (Impulsivity is merged)
    html.append('<b>4. Hyperactivity / Motor / Impulsivity:</b>')
    html.append('<ul>')
    met_hyperactive_dsm = get_met_dsm_criteria(dass_items, 'Hyperactivity/Impulsivity')
    if met_hyperactive_dsm:
        joined = ', '.join(met_hyperactive_dsm[:3]) + ('...' if len(met_hyperactive_dsm) > 3 else '')
        html.append(f'<li>DSM: Meets all {len(met_hyperactive_dsm)} criteria for Hyperactivity/Impulsivity (e.g., {joined}).</li>')
    else:
        # Calculate how many were NOT met
        total_hyper_criteria = 9 # Assuming 9 total criteria for Hyperactivity/Impulsivity
        not_met_count = total_hyper_criteria - len(met_hyperactive_dsm)
        joined = f'{not_met_count} criteria' # Simple count for now
        html.append(f'<li>DSM: Does not endorse {joined}.</li>')
    npq_imp_domain = get_npq_domain_severity(npq_scores, "Impulsive")
    npq_hyper_mod = get_npq_symptoms(npq_questions, 'Impulsive', 2)
    npq_hyper_mild = get_npq_symptoms(npq_questions, 'Impulsive', 1)
    npq_hyper_mild_only = [s for s in npq_hyper_mild if s not in npq_hyper_mod]
    html.append(f'<li>NPQ: Impulsive domain (hyperactivity items) rated "{npq_imp_domain}"; Moderate: {", ".join(npq_hyper_mod)}. Mild: {", ".join(npq_hyper_mild_only)}.</li>')
    html.append('</ul>')

    # 5. Secondary Consequences / Functional Impact Domain
    html.append('<b>5. Secondary Consequences / Functional Impact:</b>')
    html.append('<ul>')
    npq_learning_mod = get_npq_symptoms(npq_questions, 'Learning', 2)
    if npq_learning_mod: html.append(f'<li>NPQ (Learning Domain): {", ".join(npq_learning_mod)}</li>')
    html.append('<li>NPQ (Comorbid Domains - Moderate/Severe Focus):</li>')
    comorbid_symptoms = []
    for domain in ["Memory", "Anxiety", "Somatic", "Fatigue", "Sleep", "Suicide", "Pain", "Obsessions & Compulsions", "Depression", "PTSD"]:
         mod_sev = get_npq_symptoms(npq_questions, domain, 2)
         if mod_sev:
             if domain == "Suicide" and any("death or dying" in s for s in mod_sev):
                  comorbid_symptoms.append(f'<li style="color:#b91c1c;"><b>{domain}:</b> {", ".join(mod_sev)} (requires clinical attention)</li>')
             else:
                  comorbid_symptoms.append(f'<li>{domain}: {", ".join(mod_sev)}</li>')
    epworth_score = epworth[0].get('total_score') if epworth else None
    epworth_interp = epworth[0].get('interpretation', '').strip('.') if epworth else None
    if epworth_score and epworth_interp:
        comorbid_symptoms.append(f'<li>Sleep: Epworth score indicates {epworth_interp}.</li>')
    if comorbid_symptoms:
        html.extend(comorbid_symptoms)
    else:
         html.append('<li>No specific moderate/severe comorbid symptoms reported in NPQ.</li>')
    html.append('</ul>')

    # 6. Interpersonal Function Domain
    html.append('<b>6. Interpersonal Function:</b>')
    html.append('<ul>')
    met_interpersonal_dsm = [item.get('dsm_criterion').split(': ')[-1] for item in dass_items if item.get('dsm_category') == 'Hyperactivity/Impulsivity' and item.get('is_met') == 1 and item.get('dsm_criterion','').startswith(('B6:','B9:'))]
    if met_interpersonal_dsm:
        joined = ' and '.join(met_interpersonal_dsm)
        html.append(f'<li>DSM: Endorses {joined}.</li>')
    npq_social_domain = get_npq_domain_severity(npq_scores, "Social Anxiety")
    npq_social_mild = get_npq_symptoms(npq_questions, "Social Anxiety", 1)
    html.append(f'<li>NPQ (Social Anxiety): Domain rated {npq_social_domain} overall. Mild: {", ".join(npq_social_mild)}.</li>')
    npq_interpersonal_mild = get_npq_symptoms(npq_questions, "Psychotic", 1) + get_npq_symptoms(npq_questions, "Autism", 1) + get_npq_symptoms(npq_questions, "Asperger's", 1)
    interpersonal_relevant_npq = [s for s in npq_interpersonal_mild if "close to another person" in s or "social signals" in s]
    if interpersonal_relevant_npq: html.append(f'<li>NPQ (Psychotic/Autism/Asperger\'s): {", ".join(interpersonal_relevant_npq)}</li>')
    html.append('</ul>')
    html.append('</div>')
    return ''.join(html)

if __name__ == "__main__":
    file_path = '../json/40436.json' # Correct relative path from report_engine to json
    with open(file_path, 'r') as f:
        data = json.load(f)
    final_summary_string = generate_adhd_summary(data)
    print(final_summary_string)
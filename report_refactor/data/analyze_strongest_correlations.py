import pandas as pd
import os

# Load the domain-symptom correlations file
file_path = os.path.join('analysis_output', 'domain_symptom_correlations.csv')
corr_data = pd.read_csv(file_path)

# Function to get DSM criterion description
def get_dsm_criterion_description(criterion):
    criteria_descriptions = {
        'A1': 'Often fails to give close attention to details or makes careless mistakes',
        'A2': 'Often has difficulty sustaining attention in tasks or play',
        'A3': 'Often does not seem to listen when spoken to directly',
        'A4': 'Often does not follow through on instructions and fails to finish tasks',
        'A5': 'Often has difficulty organizing tasks and activities',
        'A6': 'Often avoids, dislikes, or is reluctant to engage in tasks requiring sustained mental effort',
        'A7': 'Often loses things necessary for tasks or activities',
        'A8': 'Is often easily distracted by extraneous stimuli',
        'A9': 'Is often forgetful in daily activities',
        'B1': 'Often fidgets with or taps hands or feet or squirms in seat',
        'B2': 'Often leaves seat in situations when remaining seated is expected',
        'B3': 'Often runs about or climbs in situations where inappropriate',
        'B4': 'Often unable to play or engage in leisure activities quietly',
        'B5': 'Is often "on the go" acting as if "driven by a motor"',
        'B6': 'Often talks excessively',
        'B7': 'Often blurts out an answer before a question has been completed',
        'B8': 'Often has difficulty waiting his or her turn',
        'B9': 'Often interrupts or intrudes on others'
    }
    return criteria_descriptions.get(criterion, criterion)

# Filter to include only the main domain scores
domain_patterns = [
    'Neurocognition_Index', 'Composite_Memory', 'Verbal_Memory', 'Visual_Memory',
    'Psychomotor_Speed', 'Reaction_Time', 'Complex_Attention', 'Cognitive_Flexibility',
    'Processing_Speed', 'Executive_Function', 'Reasoning', 'Working_Memory',
    'Sustained_Attention', 'Simple_Attention', 'Motor_Speed'
]

# Filter domains
main_domains = [domain for domain in corr_data['Cognitive Domain Score'].unique() 
                if any(pattern in domain for pattern in domain_patterns)]

# Open file for writing results
with open(os.path.join('analysis_output', 'top_domain_correlations.txt'), 'w') as f:
    f.write("Top 5 strongest correlations (by absolute value) for each cognitive domain:\n")
    f.write("=" * 100 + "\n\n")

    for domain in main_domains:
        # Filter for this domain
        domain_data = corr_data[corr_data['Cognitive Domain Score'] == domain].copy()
        
        # Add absolute correlation column for sorting
        domain_data['Abs Correlation'] = domain_data['Spearman R'].abs()
        
        # Sort by absolute correlation value (strongest first)
        domain_data = domain_data.sort_values('Abs Correlation', ascending=False)
        
        # Get top 5
        top_5 = domain_data.head(5)
        
        # Clean domain name for display
        clean_domain = domain.replace('percentile_', '').replace('_', ' ')
        
        f.write(f"\n{clean_domain}:\n")
        f.write("-" * 100 + "\n")
        for index, row in top_5.iterrows():
            symptom = row['Symptom Endorsed']
            description = get_dsm_criterion_description(symptom)
            corr = row['Spearman R']
            p_val = row['P-value']
            significant = "YES" if p_val < 0.05 else "NO"
            
            f.write(f"{symptom} ({description}):\n")
            f.write(f"   Correlation: {corr:.3f} | p-value: {p_val:.4f} | Significant: {significant}\n")
        
        f.write("-" * 100 + "\n")

print("Analysis complete! Results saved to analysis_output/top_domain_correlations.txt")

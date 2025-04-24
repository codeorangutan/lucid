import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np
from scipy import stats

# --- Configuration ---
DB_PATH = 'cognitive_analysis.db' # Use the correct filename
OUTPUT_DIR = 'analysis_output'
PLOTS_DIR = os.path.join(OUTPUT_DIR, 'plots')

# Create output directories if they don't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)

# --- Database Connection & Data Loading ---

def connect_db(db_path):
    """Connects to the SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        print(f"Successfully connected to database: {db_path}")
        
        # --- List tables found in the database ---
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables found in database:", tables)
        # --- End of added code ---
        
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database {db_path}: {e}")
        return None

def load_data(conn):
    """Loads necessary data tables from the database into pandas DataFrames."""
    data = {}
    tables_to_load = [
        "patients",
        "asrs_dsm_diagnosis",
        "dsm_criteria_met",
        "subtest_results", # Corrected table name
        "npq_scores",
        "cognitive_scores", # Added table
        # Add other relevant tables here if needed
    ]
    
    print("Loading data from database...")
    for table in tables_to_load:
        try:
            query = f"SELECT * FROM {table}"
            df = pd.read_sql_query(query, conn)
            data[table] = df
            print(f"- Loaded table '{table}' ({len(df)} rows)")
            # ---> ADDED PRINT STATEMENT HERE <---
            if table == 'cognitive_scores':
                print(f"Cognitive Scores columns: {df.columns.tolist()}") 
    
        except pd.io.sql.DatabaseError as e:
            print(f"- Warning: Could not load table '{table}'. Error: {e}")
            data[table] = pd.DataFrame() # Assign empty DataFrame if table doesn't exist or error occurs
        except Exception as e:
             print(f"- Error loading table '{table}': {e}")
             data[table] = pd.DataFrame()
             
    # --- Data Merging and Initial Preparation ---
    print("Merging and preparing data...")
    
    # Merge patient info with diagnosis
    if not data['patients'].empty and not data['asrs_dsm_diagnosis'].empty:
         # Ensure patient_id is string in both for consistent merging
        data['patients']['patient_id'] = data['patients']['patient_id'].astype(str)
        data['asrs_dsm_diagnosis']['patient_id'] = data['asrs_dsm_diagnosis']['patient_id'].astype(str)
        
        analysis_df = pd.merge(data['patients'], data['asrs_dsm_diagnosis'], on='patient_id', how='left')
        print(f"- Merged patients and diagnosis data ({len(analysis_df)} rows)")
    elif not data['patients'].empty:
        analysis_df = data['patients'].copy()
        analysis_df['patient_id'] = analysis_df['patient_id'].astype(str)
        # Add placeholder columns if diagnosis data is missing
        analysis_df[['inattentive_criteria_met', 'hyperactive_criteria_met', 'diagnosis']] = np.nan
        print("- Warning: Diagnosis data missing, using only patient data.")
    else:
        print("- Error: Patient data is empty. Cannot proceed with merging.")
        analysis_df = pd.DataFrame() # Start with empty if patient data is missing
        
    # Add cognitive subtest data (handle potential multiple entries per patient)
    if not data['subtest_results'].empty and not analysis_df.empty: # Use corrected key
        print("- Preparing cognitive subtest data...")
        # Ensure patient_id is string for merging
        data['subtest_results']['patient_id'] = data['subtest_results']['patient_id'].astype(str)
        
        # Pivot cognitive subtests for easier analysis (one row per patient)
        # Handle potential duplicate subtest names for a patient (e.g., if imported multiple times)
        # We'll take the mean for now, but this might need refinement depending on data quality
        
        # *** Check column names in subtest_results *** 
        # Assuming columns are: patient_id, test_name, metric, score, standard_score, percentile
        # If different, update the pivot_table call below
        print(f"Columns in subtest_results: {data['subtest_results'].columns.tolist()}") # Print columns to verify
        
        try:
            cognitive_pivot = pd.pivot_table(data['subtest_results'], # Use corrected key
                                             index='patient_id', 
                                             # Ensure these column names exist in subtest_results!
                                             columns=['subtest_name', 'metric'], 
                                             values=['score', 'standard_score', 'percentile'],
                                             aggfunc='mean') # Use mean to handle duplicates, consider alternatives
            
            # Flatten MultiIndex columns for easier access
            cognitive_pivot.columns = ['_'.join(col).strip() for col in cognitive_pivot.columns.values]
            cognitive_pivot.reset_index(inplace=True)
            
            # Merge with the main analysis DataFrame
            analysis_df = pd.merge(analysis_df, cognitive_pivot, on='patient_id', how='left')
            print(f"- Merged cognitive subtest data ({len(analysis_df)} rows)")
        except KeyError as e:
            print(f"- Error pivoting subtest_results: Missing expected column - {e}. Skipping cognitive merge.")
        except Exception as e:
             print(f"- Error processing subtest_results: {e}. Skipping cognitive merge.")
             
    else:
         print("- Warning: Cognitive subtest data (subtest_results) is empty or analysis_df is empty. Skipping merge.")

    # Add Cognitive Domain Percentiles (from cognitive_scores table)
    if not data['cognitive_scores'].empty and not analysis_df.empty:
        print("- Preparing cognitive domain percentiles...")
        cog_scores = data['cognitive_scores'].copy()
        # Ensure patient_id is string for merging
        cog_scores['patient_id'] = cog_scores['patient_id'].astype(str)

        # MODIFIED: Skip domain filtering; use all domain values from cognitive_scores
        # Print unique domain values for debugging
        print(f"DEBUG: Unique values in cognitive_scores 'domain' column: {cog_scores['domain'].unique()}")
        
        # Instead of filtering, just use all rows from cognitive_scores
        domain_scores = cog_scores.copy()

        # Find the percentile column (assuming it's named 'percentile' or similar)
        percentile_col_name = None
        for col in domain_scores.columns:
            if 'percentile' in col.lower(): # More robust check
                percentile_col_name = col
                break
        
        if percentile_col_name and 'domain' in domain_scores.columns:
            print(f"- Found domain percentile column: '{percentile_col_name}'")
            # Select relevant columns and handle potential duplicates (take first found for now)
            domain_percentiles = domain_scores[['patient_id', 'domain', percentile_col_name]].drop_duplicates(subset=['patient_id', 'domain'], keep='first')
            
            # Pivot to get domains as columns
            try:
                domain_pivot = domain_percentiles.pivot(index='patient_id', columns='domain', values=percentile_col_name)
                # Create clearer column names (e.g., percentile_Working_Memory_Index_Score)
                domain_pivot.columns = [f"percentile_{col.replace(' ', '_')}" for col in domain_pivot.columns]
                domain_pivot.reset_index(inplace=True)
                
                # Merge into analysis_df
                analysis_df = pd.merge(analysis_df, domain_pivot, on='patient_id', how='left')
                print(f"- Merged cognitive domain percentile data ({len(domain_pivot.columns) - 1} domains found, {len(analysis_df)} rows)")
            except Exception as e:
                 print(f"- Error pivoting cognitive domain scores: {e}. Check for duplicate patient_id/domain combinations.")

        else:
            print("- Warning: Could not find a suitable percentile column or 'domain' column in cognitive_scores for domain analysis.")
    else:
        print("- Warning: Cognitive scores data is empty or analysis_df is empty. Skipping domain percentile merge.")

    # Add NPQ scores (handle potential multiple entries per patient)
    if not data['npq_scores'].empty and not analysis_df.empty:
        print("- Preparing NPQ scores data...")
        # Print npq_scores table structure to debug
        print(f"NPQ scores columns: {data['npq_scores'].columns.tolist()}")
        print(f"NPQ scores sample data:\n{data['npq_scores'].head()}")
        
        # Ensure patient_id is string for merging
        data['npq_scores']['patient_id'] = data['npq_scores']['patient_id'].astype(str)
        
        # Create better column names for the pivoted data
        # Replace pivot_table with a more reliable approach
        try:
            # Group by patient_id and domain, taking the most recent score if there are duplicates
            # Sort by timestamp if available, otherwise take the highest score as the most recent assessment
            if 'timestamp' in data['npq_scores'].columns:
                npq_latest = data['npq_scores'].sort_values(['patient_id', 'domain', 'timestamp'], 
                                                         ascending=[True, True, False]).drop_duplicates(['patient_id', 'domain'])
            else:
                # Without timestamp, use the highest score as most recent
                npq_latest = data['npq_scores'].sort_values(['patient_id', 'domain', 'score'], 
                                                         ascending=[True, True, False]).drop_duplicates(['patient_id', 'domain'])
            
            # Pivot to put each domain in its own column
            npq_pivot = npq_latest.pivot(index='patient_id', columns='domain', values='score')
            
            # Add prefix to column names
            npq_pivot.columns = [f'npq_{col.lower().replace(" ", "_")}_score' for col in npq_pivot.columns]
            npq_pivot.reset_index(inplace=True)
            
            # Calculate severity level based on score thresholds (assuming higher score = more severe)
            # Define severity cutoffs (example - adjust based on actual scale)
            severity_data = []
            
            # Process each domain in the original data
            for domain in npq_latest['domain'].unique():
                domain_data = npq_latest[npq_latest['domain'] == domain]
                
                # Define severity based on score (you might need to adjust these thresholds)
                # For now using simple quartile-based thresholds
                for _, row in domain_data.iterrows():
                    score = row['score']
                    # Determine severity based on score
                    if score >= 200:  # Severe threshold
                        severity = 'Severe'
                    elif score >= 150:  # Moderate threshold
                        severity = 'Moderate'
                    elif score >= 100:  # Mild threshold
                        severity = 'Mild'
                    else:
                        severity = 'Not a problem'
                    
                    severity_data.append({
                        'patient_id': row['patient_id'],
                        'domain': domain,
                        'score': score,
                        'severity': severity
                    })
            
            # Create DataFrame from severity data
            severity_df = pd.DataFrame(severity_data)
            
            # Merge with the main analysis DataFrame
            analysis_df = pd.merge(analysis_df, npq_pivot, on='patient_id', how='left')
            print(f"- Merged NPQ scores data ({len(analysis_df)} rows)")
            
            # Save severity data for later analysis
            data['npq_severity'] = severity_df
            
        except Exception as e:
            print(f"- Error processing NPQ scores: {e}")
    else:
        print("- Warning: NPQ scores data is empty or analysis_df is empty. Skipping merge.")
         
    # Store raw dataframes as well
    data['analysis_df'] = analysis_df 
    
    print("Data loading and preparation complete.")
    return data

# --- Foundational Analysis Functions ---

def save_descriptives(df, filename, title="Descriptive Statistics"):
    """Saves descriptive statistics to a text file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, 'w') as f:
            f.write(f"--- {title} ---\n\n")
            f.write(df.to_string())
        print(f"Saved descriptive statistics to: {filepath}")
    except Exception as e:
        print(f"Error saving descriptive statistics to {filepath}: {e}")

def analyze_demographics(patients_df):
    """Performs descriptive analysis on patient demographics."""
    print("\n--- Analyzing Demographics ---")
    if 'age' in patients_df.columns:
        desc_stats = patients_df['age'].describe()
        print("Age Statistics:")
        print(desc_stats)
        save_descriptives(desc_stats.to_frame(), "demographics_age_stats.txt", "Age Statistics")
        
        # Plot age distribution
        plt.figure(figsize=(8, 5))
        sns.histplot(patients_df['age'].dropna(), kde=True)
        plt.title('Age Distribution of Patients')
        plt.xlabel('Age')
        plt.ylabel('Frequency')
        plot_path = os.path.join(PLOTS_DIR, 'age_distribution.png')
        plt.savefig(plot_path)
        plt.close()
        print(f"Saved age distribution plot to: {plot_path}")
    else:
        print("- Age data not found.")
        
    # Add analysis for other demographics like gender if available

def analyze_adhd_subtypes(diagnosis_df):
    """Analyzes the distribution of ADHD subtypes."""
    print("\n--- Analyzing ADHD Subtype Distribution ---")
    if 'diagnosis' in diagnosis_df.columns:
        subtype_counts = diagnosis_df['diagnosis'].value_counts(dropna=False)
        subtype_percentages = diagnosis_df['diagnosis'].value_counts(normalize=True, dropna=False) * 100
        
        subtype_summary = pd.DataFrame({'Count': subtype_counts, 'Percentage': subtype_percentages.round(2)})
        print(subtype_summary)
        save_descriptives(subtype_summary, "adhd_subtype_distribution.txt", "ADHD Subtype Distribution")

        # Plot subtype distribution
        plt.figure(figsize=(10, 6))
        sns.barplot(x=subtype_summary.index.astype(str), y=subtype_summary['Count']) # Ensure index is string for plotting
        plt.title('Distribution of ADHD Subtypes')
        plt.xlabel('ADHD Diagnosis')
        plt.ylabel('Number of Patients')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plot_path = os.path.join(PLOTS_DIR, 'adhd_subtype_distribution.png')
        plt.savefig(plot_path)
        plt.close()
        print(f"Saved subtype distribution plot to: {plot_path}")
    else:
        print("- Diagnosis data not found.")

def analyze_cognitive_performance(cognitive_df):
    """Performs descriptive analysis on cognitive test scores."""
    print("\n--- Analyzing Cognitive Performance ---")
    score_types = ['score', 'standard_score', 'percentile']
    
    if cognitive_df.empty:
        print("- Cognitive subtest data is empty. Skipping analysis.")
        return

    all_desc_stats = {}
    for score_type in score_types:
         # Select columns related to the current score type
        score_cols = [col for col in cognitive_df.columns 
                      if score_type in col.split('_')]
        
        if not score_cols:
            print(f"- No columns found for score type: {score_type}")
            continue
            
        desc_stats = cognitive_df[score_cols].describe().transpose()
        # Add median explicitly as describe() doesn't show it prominently in transpose
        desc_stats['median'] = cognitive_df[score_cols].median()
        desc_stats = desc_stats[['count', 'mean', 'std', 'min', '25%', 'median', '75%', 'max']] # Reorder columns
        
        print(f"\nDescriptive Statistics for Cognitive Subtests ({score_type.replace('_', ' ').title()}s):")
        print(desc_stats)
        save_descriptives(desc_stats, f"cognitive_subtest_{score_type}_stats.txt", f"Cognitive Subtest {score_type.replace('_', ' ').title()} Statistics")
        all_desc_stats[score_type] = desc_stats
        
        # Visualize distributions for standard scores (most comparable)
        if score_type == 'standard_score' and not desc_stats.empty:
            print(f"\nGenerating boxplots for Cognitive Subtest Standard Scores...")
            # Limit the number of boxplots per figure if there are too many tests
            num_plots = len(score_cols)
            plots_per_fig = 10 # Adjust as needed
            num_figs = (num_plots + plots_per_fig - 1) // plots_per_fig

            for i in range(num_figs):
                start_idx = i * plots_per_fig
                end_idx = min((i + 1) * plots_per_fig, num_plots)
                current_cols = score_cols[start_idx:end_idx]
                
                plt.figure(figsize=(15, 8))
                # Prepare data for boxplot - melt or select columns
                plot_data = cognitive_df[current_cols].copy()
                # Clean up column names for plotting
                plot_data.columns = [col.replace('_standard_score', '').replace('_', ' ') for col in current_cols] 
                
                sns.boxplot(data=plot_data, orient='h')
                plt.title(f'Distribution of Cognitive Subtest Standard Scores (Part {i+1})')
                plt.xlabel('Standard Score')
                plt.tight_layout()
                plot_path = os.path.join(PLOTS_DIR, f'cognitive_std_score_distribution_part_{i+1}.png')
                plt.savefig(plot_path)
                plt.close()
                print(f"Saved standard score distribution plot (Part {i+1}) to: {plot_path}")

    return all_desc_stats


def analyze_adhd_symptoms(diagnosis_df, criteria_df):
    """Analyzes ADHD symptom severity based on criteria met."""
    print("\n--- Analyzing ADHD Symptom Severity (Criteria Met) ---")
    
    summary_stats = {}
    
    # 1. From asrs_dsm_diagnosis table (overall counts)
    if not diagnosis_df.empty and all(col in diagnosis_df.columns for col in ['inattentive_criteria_met', 'hyperactive_criteria_met']):
        print("\nCriteria Counts from asrs_dsm_diagnosis:")
        criteria_cols = ['inattentive_criteria_met', 'hyperactive_criteria_met']
        desc_stats = diagnosis_df[criteria_cols].describe()
        print(desc_stats)
        save_descriptives(desc_stats, "adhd_criteria_count_stats.txt", "ADHD Criteria Met Count Statistics")
        summary_stats['overall_counts'] = desc_stats
        
        # Plot distributions
        plt.figure(figsize=(12, 5))
        
        plt.subplot(1, 2, 1)
        sns.histplot(diagnosis_df['inattentive_criteria_met'].dropna(), kde=False, bins=range(11))
        plt.title('Inattentive Criteria Met')
        plt.xlabel('Number of Criteria (0-9)')
        plt.ylabel('Frequency')
        plt.xticks(range(10))
        
        plt.subplot(1, 2, 2)
        sns.histplot(diagnosis_df['hyperactive_criteria_met'].dropna(), kde=False, bins=range(11))
        plt.title('Hyperactive Criteria Met')
        plt.xlabel('Number of Criteria (0-9)')
        plt.ylabel('Frequency')
        plt.xticks(range(10))
        
        plt.tight_layout()
        plot_path = os.path.join(PLOTS_DIR, 'adhd_criteria_met_distribution.png')
        plt.savefig(plot_path)
        plt.close()
        print(f"Saved criteria met distribution plot to: {plot_path}")
        
    else:
         print("- Criteria count data not found in asrs_dsm_diagnosis.")
         
    # 2. From dsm_criteria_met table (specific criteria frequencies)
    if not criteria_df.empty and all(col in criteria_df.columns for col in ['dsm_criterion', 'is_met']):
        print("\nFrequencies of Specific DSM Criteria Met:")
        # Calculate the percentage of patients meeting each criterion
        criteria_met_counts = criteria_df[criteria_df['is_met'] == 1]['dsm_criterion'].value_counts()
        total_patients_evaluated = criteria_df['patient_id'].nunique() # Get unique patients in this table
        
        if total_patients_evaluated > 0:
            criteria_met_perc = (criteria_met_counts / total_patients_evaluated) * 100
            criteria_freq_summary = pd.DataFrame({'Count Met': criteria_met_counts, 'Percentage Met (%)': criteria_met_perc.round(2)})
            criteria_freq_summary = criteria_freq_summary.sort_index() # Sort by criterion name
            print(criteria_freq_summary)
            save_descriptives(criteria_freq_summary, "dsm_specific_criteria_freq.txt", "Specific DSM Criteria Met Frequencies")
            summary_stats['specific_criteria'] = criteria_freq_summary
            
            # Plot frequencies (maybe top N or split by Inattentive/Hyperactive)
            plt.figure(figsize=(10, 12)) # Adjust size as needed
            sns.barplot(y=criteria_freq_summary.index.astype(str), x=criteria_freq_summary['Percentage Met (%)'], orient='h')
            plt.title('Percentage of Patients Meeting Specific DSM Criteria')
            plt.xlabel('Percentage Met (%)')
            plt.ylabel('DSM Criterion')
            plt.tight_layout()
            plot_path = os.path.join(PLOTS_DIR, 'dsm_specific_criteria_met_percentage.png')
            plt.savefig(plot_path)
            plt.close()
            print(f"Saved specific criteria met plot to: {plot_path}")
            
        else:
            print("- No patients found in dsm_criteria_met table.")

    else:
        print("- Specific DSM criteria data not found or incomplete.")
        
    return summary_stats

def analyze_npq_comorbidity(npq_scores_df):
    """Analyzes NPQ scores for potential comorbidities."""
    print("\n--- Analyzing NPQ Comorbidity Scores ---")
    
    if npq_scores_df.empty or 'domain' not in npq_scores_df.columns or 'severity' not in npq_scores_df.columns:
        print("- NPQ scores data is empty or missing required columns ('domain', 'severity'). Skipping analysis.")
        return None

    # Descriptive stats for numeric scores per domain
    print("\nDescriptive Statistics for NPQ Domain Scores:")
    npq_numeric_stats = npq_scores_df.groupby('domain')['score'].describe()
    # Add median
    npq_numeric_stats['median'] = npq_scores_df.groupby('domain')['score'].median()
    npq_numeric_stats = npq_numeric_stats[['count', 'mean', 'std', 'min', '25%', 'median', '75%', 'max']] # Reorder columns
    
    print(npq_numeric_stats)
    save_descriptives(npq_numeric_stats, "npq_domain_score_stats.txt", "NPQ Domain Score Statistics")

    # Frequency of severity levels per domain
    print("\nFrequency of NPQ Severity Levels per Domain:")
    severity_counts = npq_scores_df.groupby('domain')['severity'].value_counts().unstack(fill_value=0)
    
    # Calculate percentages
    severity_percentages = severity_counts.apply(lambda x: (x / x.sum() * 100).round(2), axis=1)
    
    print("Counts:")
    print(severity_counts)
    print("\nPercentages:")
    print(severity_percentages)
    
    save_descriptives(severity_counts, "npq_severity_counts.txt", "NPQ Severity Level Counts per Domain")
    save_descriptives(severity_percentages, "npq_severity_percentages.txt", "NPQ Severity Level Percentages per Domain")

    # Plot severity distributions
    # Stacked bar chart for severity percentages might be good
    try:
        # Ensure severity levels are ordered if possible (e.g., Mild, Moderate, Severe) - needs specific levels
        # For now, plot as is
        severity_percentages.plot(kind='bar', stacked=True, figsize=(12, 7))
        plt.title('Distribution of NPQ Severity Levels Across Domains')
        plt.xlabel('NPQ Domain')
        plt.ylabel('Percentage of Patients (%)')
        plt.xticks(rotation=45, ha='right')
        plt.legend(title='Severity', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plot_path = os.path.join(PLOTS_DIR, 'npq_severity_distribution.png')
        plt.savefig(plot_path)
        plt.close()
        print(f"Saved NPQ severity distribution plot to: {plot_path}")
    except Exception as e:
        print(f"Error generating NPQ severity plot: {e}")
        
    return {'numeric_stats': npq_numeric_stats, 'severity_counts': severity_counts, 'severity_percentages': severity_percentages}

def analyze_cognitive_by_subtype(all_data):
    """Compares cognitive performance across ADHD subtypes using Kruskal-Wallis test."""
    analysis_df = all_data.get('analysis_df', pd.DataFrame())
    if analysis_df.empty or 'diagnosis' not in analysis_df.columns:
        print("- Skipping subtype cognitive analysis: Missing data or diagnosis column.")
        return

    # Identify cognitive score columns (look for standard_score or percentile columns first)
    cognitive_cols = [col for col in analysis_df.columns 
                      if ('standard_score' in col or 'percentile' in col) and 
                         not col.startswith('npq_')] # Exclude NPQ
                      
    # If no standard scores/percentiles, fall back to raw scores (less ideal)
    if not cognitive_cols:
        cognitive_cols = [col for col in analysis_df.columns 
                          if ('score' in col) and 
                             not col.startswith('npq_') and 
                             col not in ['epworth_total_score', 'patient_id']] # Exclude non-cognitive scores

    if not cognitive_cols:
        print("- Skipping subtype cognitive analysis: No suitable cognitive score columns found.")
        return
        
    print(f"- Comparing {len(cognitive_cols)} cognitive scores across subtypes:")
    # print(f"  Scores being compared: {cognitive_cols}") # Optional: print list of scores

    subtypes = analysis_df['diagnosis'].unique()
    # Ensure we have at least 2 subtypes with enough data for comparison
    subtype_counts = analysis_df['diagnosis'].value_counts()
    valid_subtypes = subtype_counts[subtype_counts >= 5].index.tolist() # Require min 5 per group

    if len(valid_subtypes) < 2:
        print("- Skipping subtype cognitive analysis: Need at least two subtypes with >= 5 participants for comparison.")
        print(f"  Subtype counts: {subtype_counts}")
        return

    analysis_subset = analysis_df[analysis_df['diagnosis'].isin(valid_subtypes)].copy()
    print(f"- Performing analysis on subtypes: {valid_subtypes}")

    results = []
    for col in cognitive_cols:
        # Ensure column data is numeric and handle missing values
        analysis_subset[col] = pd.to_numeric(analysis_subset[col], errors='coerce')
        analysis_subset.dropna(subset=[col], inplace=True)
        
        # Prepare data for Kruskal-Wallis: list of arrays, one for each group
        groups = [analysis_subset[analysis_subset['diagnosis'] == subtype][col].values 
                  for subtype in valid_subtypes]
        
        # Check if all groups have data after dropping NaNs
        if not all(len(g) > 0 for g in groups):
            # print(f"  Skipping {col}: Not enough data in all groups after handling NaNs.")
            continue

        try:
            stat, p_value = stats.kruskal(*groups)
            if p_value < 0.05:
                # Find which groups are different (example using mean ranks)
                group_means = [(subtype, analysis_subset[analysis_subset['diagnosis'] == subtype][col].mean()) 
                               for subtype in valid_subtypes]
                group_means.sort(key=lambda x: x[1], reverse=True)
                
                results.append({
                    'Cognitive Score': col,
                    'Kruskal-Wallis H': stat,
                    'P-value': p_value,
                    'Significant Difference': 'Yes',
                    'Mean Rank Order': ", ".join([f"{name} ({mean:.2f})" for name, mean in group_means])
                })
                # Note: Proper post-hoc tests (Dunn's) would be better here for specific pairwise comparisons
            # else: # Optionally store non-significant results too
            #     results.append({
            #         'Cognitive Score': col,
            #         'Kruskal-Wallis H': stat,
            #         'P-value': p_value,
            #         'Significant Difference': 'No',
            #          'Mean Rank Order': 'N/A'
            #     })
        except ValueError as e:
            # Often happens if a group has zero variance or insufficient data
            # print(f"  Skipping {col} due to error during Kruskal-Wallis test: {e}")
            pass 
        except Exception as e:
            print(f"  Error processing {col}: {e}")

    if results:
        results_df = pd.DataFrame(results)
        print("\nSignificant Differences in Cognitive Scores Across ADHD Subtypes (Kruskal-Wallis p < 0.05):")
        print(results_df.to_string(index=False))
        save_descriptives(results_df, "subtype_cognitive_differences.csv", "Cognitive Score Differences by ADHD Subtype")
    else:
        print("\n- No significant differences found in cognitive scores across ADHD subtypes (using Kruskal-Wallis test).")

# --- Add Function: Analyze Correlation between ADHD Symptoms and Cognitive Performance ---
def analyze_symptom_cognition_correlation(all_data):
    """Calculates Spearman correlations between individual DSM symptoms endorsed and cognitive scores."""
    analysis_df = all_data.get('analysis_df', pd.DataFrame()).copy() # Work on a copy
    criteria_df = all_data.get('dsm_criteria_met', pd.DataFrame())
    
    if analysis_df.empty or criteria_df.empty:
        print("- Skipping symptom-cognition correlation: Missing analysis_df or dsm_criteria_met data.")
        return

    # --- 1. Reshape DSM Criteria Data ---
    print("- Reshaping DSM criteria data for correlation...")
    criteria_df['patient_id'] = criteria_df['patient_id'].astype(str)
    analysis_df['patient_id'] = analysis_df['patient_id'].astype(str)
    
    # --- Debug: Print columns of criteria_df ---
    print(f"Original columns in dsm_criteria_met: {criteria_df.columns.tolist()}")
    # --- End Debug ---
    
    # Check if expected columns exist
    required_cols = ['patient_id', 'dsm_criterion', 'met']
    missing_cols = [col for col in required_cols if col not in criteria_df.columns]
    
    if missing_cols:
        print(f"- Missing expected columns in dsm_criteria_met: {missing_cols}. Found: {criteria_df.columns.tolist()}")
        # Attempting to find alternative names
        renamed = False
        if 'met' in missing_cols and 'is_met' in criteria_df.columns:
            print("  -> Found 'is_met', renaming to 'met' for processing.")
            criteria_df.rename(columns={'is_met': 'met'}, inplace=True)
            renamed = True
            # Re-check missing columns after rename
            missing_cols = [col for col in required_cols if col not in criteria_df.columns]
            
        if 'dsm_criterion' in missing_cols and 'criterion' in criteria_df.columns:
            print("  -> Found 'criterion', renaming to 'dsm_criterion' for processing.")
            criteria_df.rename(columns={'criterion': 'dsm_criterion'}, inplace=True)
            renamed = True
            # Re-check missing columns after rename
            missing_cols = [col for col in required_cols if col not in criteria_df.columns]
            
        # If columns are still missing after trying to rename, we cannot proceed
        if missing_cols:
             print(f"- Cannot proceed. Still missing required columns: {missing_cols}")
             return
             
    # Filter for met criteria only
    met_criteria = criteria_df[criteria_df['met'] == 1].copy()
    
    # Create a simplified criterion name for columns (e.g., A1a, A2b)
    # This assumes criterion text starts like "A1a: ...", "A2b: ...", etc.
    try:
        met_criteria['symptom_code'] = met_criteria['dsm_criterion'].str.extract(r'^([A-H][1-9][a-z]?)\s*[:.)-]?', expand=False).fillna('unknown_symptom')
    except AttributeError:
        print("- Error extracting symptom codes from 'dsm_criterion'. Check column format.")
        met_criteria['symptom_code'] = 'dsm_symptom_' + met_criteria.index.astype(str) # Fallback naming

    # Pivot to create columns for each symptom code
    # Use crosstab for frequency count (will be 0 or 1 since we filtered met==1 and patient_id/symptom_code should be unique)
    symptom_pivot = pd.crosstab(met_criteria['patient_id'], met_criteria['symptom_code'])
    
    # Ensure column names are suitable (prefix)
    symptom_pivot.columns = [f'dsm_{col}_met' for col in symptom_pivot.columns]
    symptom_pivot.reset_index(inplace=True)
    
    # Merge symptom pivot table into the main analysis dataframe
    analysis_df = pd.merge(analysis_df, symptom_pivot, on='patient_id', how='left')
    # Fill NaNs with 0 for patients who didn't meet specific criteria
    symptom_cols = [col for col in symptom_pivot.columns if col != 'patient_id']
    analysis_df[symptom_cols] = analysis_df[symptom_cols].fillna(0).astype(int)
    
    if not symptom_cols:
        print("- Skipping symptom-cognition correlation: No individual symptom columns created.")
        return
        
    print(f"  Created {len(symptom_cols)} individual DSM symptom columns (e.g., dsm_A1a_met)...")

    # --- 2. Select Cognitive Scores ---
    # (Keep existing logic - prioritize percentile/standard scores)
    cognitive_cols = [col for col in analysis_df.columns 
                      if ('standard_score' in col or 'percentile' in col) and 
                         not col.startswith('npq_')] 
                         
    if not cognitive_cols:
        cognitive_cols = [col for col in analysis_df.columns 
                          if ('score' in col) and 
                             not col.startswith('npq_') and 
                             col not in symptom_cols and # Exclude the symptom cols themselves
                             col not in ['epworth_total_score', 'patient_id', 'age']] # Exclude non-cognitive

    if not cognitive_cols:
        print("- Skipping symptom-cognition correlation: No suitable cognitive score columns found.")
        return
        
    print(f"- Calculating correlations for {len(symptom_cols)} symptoms and {len(cognitive_cols)} cognitive scores...")

    # --- 3. Calculate Correlations ---
    # data_for_corr = analysis_df[symptom_cols + cognitive_cols] # Use newly created symptom_cols
    data_for_corr = analysis_df.copy()
    
    # Ensure all data is numeric, coercing errors to NaN
    for col in symptom_cols + cognitive_cols:
        if col in data_for_corr.columns:
            data_for_corr[col] = pd.to_numeric(data_for_corr[col], errors='coerce')
            
    # Drop rows with any NaNs in the columns used for correlation
    # Need to be careful here as many symptoms might be 0 for many patients
    # Correlation function handles pairwise deletion by default, which is better here.
    # data_for_corr.dropna(inplace=True) 
    
    # Select only the columns needed for correlation AFTER converting to numeric
    valid_symptom_cols = [col for col in symptom_cols if col in data_for_corr.columns]
    valid_cognitive_cols = [col for col in cognitive_cols if col in data_for_corr.columns]
    
    if not valid_symptom_cols or not valid_cognitive_cols:
        print("- Skipping: Not enough valid columns remain for correlation.")
        return
        
    data_for_corr_final = data_for_corr[valid_symptom_cols + valid_cognitive_cols]

    # Calculate Spearman correlation matrix
    corr_matrix = data_for_corr_final.corr(method='spearman')

    # Calculate p-values (using scipy.stats.spearmanr for pairwise p-values)
    p_values = pd.DataFrame(np.nan, index=corr_matrix.index, columns=corr_matrix.columns)
    for r in valid_symptom_cols:
        for c in valid_cognitive_cols:
            subset = data_for_corr_final[[r, c]].dropna()
            if subset.shape[0] >= 5: # Need at least 5 pairs for meaningful correlation
                try:
                    corr, p = stats.spearmanr(subset[r], subset[c])
                    p_values.loc[r, c] = p
                except ValueError: # Handle cases with zero variance if any
                    p_values.loc[r, c] = np.nan
            else:
                p_values.loc[r, c] = np.nan
                
    # Focus on correlations between symptoms and cognition
    corr_subset = corr_matrix.loc[valid_symptom_cols, valid_cognitive_cols]
    p_value_subset = p_values.loc[valid_symptom_cols, valid_cognitive_cols]

    # --- ADDED: Extract and save ALL domain-specific correlations (before filtering for significance) ---
    print(f"DEBUG: Valid cognitive columns for correlation: {valid_cognitive_cols}") 
    
    # UPDATED: Use correct patterns for domain column names
    domain_patterns = [
        'Neurocognition_Index', 'Composite_Memory', 'Verbal_Memory', 'Visual_Memory',
        'Psychomotor_Speed', 'Reaction_Time', 'Complex_Attention', 'Cognitive_Flexibility',
        'Processing_Speed', 'Executive_Function', 'Reasoning', 'Working_Memory',
        'Sustained_Attention', 'Simple_Attention', 'Motor_Speed'
    ]
    domain_cog_cols = [col for col in valid_cognitive_cols if any(pattern in col for pattern in domain_patterns)]
    print(f"DEBUG: Identified domain columns: {domain_cog_cols}") 
    if domain_cog_cols:
        all_domain_corrs = []
        for symptom_col in valid_symptom_cols:
            for cog_col in domain_cog_cols:
                r = corr_subset.loc[symptom_col, cog_col]
                p = p_value_subset.loc[symptom_col, cog_col]
                # Include all, even if p is NaN or >= 0.05
                all_domain_corrs.append({
                    'Symptom Endorsed': symptom_col.replace('dsm_', '').replace('_met', ''), # Clean name
                    'Cognitive Domain Score': cog_col,
                    'Spearman R': r,
                    'P-value': p
                })
        
        if all_domain_corrs:
            all_domain_df = pd.DataFrame(all_domain_corrs).sort_values(by=['Cognitive Domain Score', 'Symptom Endorsed'])
            domain_output_filename = os.path.join(OUTPUT_DIR, 'domain_symptom_correlations.csv')
            try:
                all_domain_df.to_csv(domain_output_filename, index=False)
                print(f"Saved ALL domain-specific symptom correlations to: {domain_output_filename}")
            except Exception as e:
                print(f"- Error saving all domain correlations: {e}")
        else:
             print("- No domain cognitive columns found to extract correlations.")
    else:
        print("- No cognitive columns identified as domain scores.")
    # --- END ADDED SECTION ---
        

    # --- 4. Report Significant Findings ---
    significant_corrs = []
    for symptom_col in valid_symptom_cols:
        for cog_col in valid_cognitive_cols:
            r = corr_subset.loc[symptom_col, cog_col]
            p = p_value_subset.loc[symptom_col, cog_col]
            if pd.notna(p) and p < 0.05:
                significant_corrs.append({
                    'Symptom Endorsed': symptom_col.replace('dsm_', '').replace('_met', ''), # Clean name
                    'Cognitive Score': cog_col,
                    'Spearman R': r,
                    'P-value': p
                })

    if significant_corrs:
        significant_df = pd.DataFrame(significant_corrs).sort_values(by='P-value')
        print("\nSignificant Correlations between Specific DSM Symptom Endorsement and Cognitive Scores (Spearman p < 0.05):")
        print(significant_df.to_string(index=False))
        save_descriptives(significant_df, "individual_symptom_cognition_correlations.csv", "Significant Correlations: Individual Symptoms vs Cognition")
        
    else:
        print("\n- No significant correlations found between individual DSM symptom endorsements and cognitive scores.")

    # --- 5. Visualize ---
    if not corr_subset.empty:
        try:
            # Limit heatmap size if too many columns
            max_cog_cols_heatmap = 40
            if len(valid_cognitive_cols) > max_cog_cols_heatmap:
                print(f"- Limiting heatmap to first {max_cog_cols_heatmap} cognitive columns due to size.")
                corr_subset_viz = corr_subset.iloc[:, :max_cog_cols_heatmap]
            else:
                corr_subset_viz = corr_subset
                
            plt.figure(figsize=(max(10, corr_subset_viz.shape[1] * 0.4), max(8, corr_subset_viz.shape[0] * 0.3)))
            sns.heatmap(corr_subset_viz, annot=False, cmap='coolwarm', fmt='.2f', linewidths=.5, cbar=True, center=0)
            plt.title('Spearman Correlation: Individual DSM Symptoms vs. Cognitive Scores (Subset)')
            plt.xticks(rotation=60, ha='right', fontsize=8)
            plt.yticks(rotation=0, fontsize=8)
            plt.tight_layout()
            plot_filename = os.path.join(PLOTS_DIR, 'individual_symptom_cognition_corr_heatmap.png')
            plt.savefig(plot_filename, bbox_inches='tight', dpi=150)
            plt.close()
            print(f"\nSaved correlation heatmap (subset) to: {plot_filename}")
        except Exception as e:
            print(f"- Error generating correlation heatmap: {e}")
    else:
        print("- Skipping heatmap generation as correlation subset is empty.")
# --- End of Added Function ---


# --- Add Function: Analyze Symptoms for Low Cognitive Performers ---
def analyze_low_cognition_symptoms(all_data, analyze_domains=False):
    """Identifies common symptoms among patients scoring < 25th percentile on cognitive tests OR domains."""
    # Ensure the analysis_df has the pivoted symptoms from the previous step
    # It might be safer to recalculate/reshape here if function order changes
    analysis_df = all_data.get('analysis_df', pd.DataFrame()).copy()
    criteria_df = all_data.get('dsm_criteria_met', pd.DataFrame())
    
    if analysis_df.empty or criteria_df.empty:
        print("- Skipping low cognition symptom analysis: Missing analysis_df or dsm_criteria_met data.")
        return

    # --- 1. Ensure Symptom Columns Exist (Reshape if necessary) ---
    # Check if symptom columns (dsm_..._met) already exist from previous correlation step
    symptom_cols_check = [col for col in analysis_df.columns if col.startswith('dsm_') and col.endswith('_met')]
    
    if not symptom_cols_check:
        print("- Reshaping DSM criteria data as symptom columns not found in analysis_df...")
        # (Repeat the reshaping logic from analyze_symptom_cognition_correlation)
        criteria_df['patient_id'] = criteria_df['patient_id'].astype(str)
        analysis_df['patient_id'] = analysis_df['patient_id'].astype(str)
        
        required_cols = ['patient_id', 'dsm_criterion', 'met']
        missing_cols = [col for col in required_cols if col not in criteria_df.columns]
        if missing_cols:
            if 'met' in missing_cols and 'is_met' in criteria_df.columns:
                criteria_df.rename(columns={'is_met': 'met'}, inplace=True)
                missing_cols = [col for col in required_cols if col not in criteria_df.columns]
            if 'dsm_criterion' in missing_cols and 'criterion' in criteria_df.columns:
                 criteria_df.rename(columns={'criterion': 'dsm_criterion'}, inplace=True)
                 missing_cols = [col for col in required_cols if col not in criteria_df.columns]
            if missing_cols:
                 print(f"- Cannot reshape. Still missing required columns: {missing_cols}")
                 return

        met_criteria = criteria_df[criteria_df['met'] == 1].copy()
        try:
            met_criteria['symptom_code'] = met_criteria['dsm_criterion'].str.extract(r'^([A-H][1-9][a-z]?)\s*[:.)-]?', expand=False).fillna('unknown_symptom')
        except AttributeError:
            print("- Error extracting symptom codes from 'dsm_criterion'. Check column format.")
            met_criteria['symptom_code'] = 'dsm_symptom_' + met_criteria.index.astype(str) # Fallback naming

        # Pivot to create columns for each symptom code
        # Use crosstab for frequency count (will be 0 or 1 since we filtered met==1 and patient_id/symptom_code should be unique)
        symptom_pivot = pd.crosstab(met_criteria['patient_id'], met_criteria['symptom_code'])
        
        # Ensure column names are suitable (prefix)
        symptom_pivot.columns = [f'dsm_{col}_met' for col in symptom_pivot.columns]
        symptom_pivot.reset_index(inplace=True)
        
        # Merge symptom pivot table into the main analysis dataframe
        analysis_df = pd.merge(analysis_df, symptom_pivot, on='patient_id', how='left')
        symptom_cols = [col for col in symptom_pivot.columns if col != 'patient_id']
        analysis_df[symptom_cols] = analysis_df[symptom_cols].fillna(0).astype(int)
        print(f"  Reshaped and added {len(symptom_cols)} symptom columns.")
    else:
        symptom_cols = symptom_cols_check
        print("- Found existing individual symptom columns.")
        
    if not symptom_cols:
        print("- Skipping low cognition symptom analysis: No individual symptom columns available.")
        return
        
    # --- 2. Identify Cognitive Percentile Columns (Subtest or Domain) ---
    potential_domain_patterns = ['Index Score', 'Domain Score'] # Define domain patterns outside the if/else to ensure scope

    if analyze_domains:
        # Attempt to identify domain score percentiles (adjust patterns as needed)
        # Common patterns already defined above
        # Also consider NPQ percentiles if they represent domains
        percentile_cols = [
            col for col in analysis_df.columns 
            if 'percentile' in col and 
            (any(pattern in col for pattern in potential_domain_patterns) or col.startswith('npq_percentile'))
        ]
        analysis_type = "Domain"
        output_filename = "low_domain_score_symptom_profile.csv"
        if not percentile_cols:
             # Fallback to NPQ if specific domain names weren't found
             percentile_cols = [col for col in analysis_df.columns if col.startswith('npq_percentile')]
             if percentile_cols:
                 print("- Warning: Using NPQ percentile columns as domain scores.")
             else:
                 print("- Skipping low domain score symptom analysis: No domain percentile columns identified.")
                 return
    else:
        # Original behavior: Use subtest percentiles (excluding NPQ)
        percentile_cols = [col for col in analysis_df.columns if 'percentile' in col and not col.startswith('npq_') and not any(pattern in col for pattern in potential_domain_patterns)]
        analysis_type = "Subtest"
        output_filename = "low_subtest_cognition_symptom_profile.csv"
        if not percentile_cols:
            print("- Skipping low subtest cognition symptom analysis: No subtest percentile columns found.")
            return
        
    print(f"- Analyzing symptoms for low performers (<25th percentile) on {len(percentile_cols)} cognitive {analysis_type} scores...")
    
    # --- 3. Analyze Each Score ---
    low_performer_symptoms = []
    min_low_performers = 5 # Minimum number of patients scoring <25 for analysis

    for test_col in percentile_cols:
        # Ensure the column is numeric
        analysis_df[test_col] = pd.to_numeric(analysis_df[test_col], errors='coerce')
        
        # Identify low performers (handle NaNs)
        low_performers_mask = (analysis_df[test_col] < 25) & analysis_df[test_col].notna()
        low_performers_df = analysis_df.loc[low_performers_mask]
        n_low_performers = low_performers_df.shape[0]
        
        if n_low_performers < min_low_performers:
            # print(f"  - Skipping test '{test_col}': Only {n_low_performers} performers < 25th percentile (min {min_low_performers}).")
            continue
            
        # Calculate symptom frequencies and proportions within this group
        symptom_freq = low_performers_df[symptom_cols].sum()
        symptom_prop = (symptom_freq / n_low_performers).round(3)
        
        # Store results for this test/domain
        for symptom in symptom_cols:
            if symptom_freq[symptom] > 0: # Only report symptoms that were actually endorsed
                low_performer_symptoms.append({
                    f'Cognitive {analysis_type} Score (Percentile < 25)': test_col.replace('percentile_', ''),
                    'Symptom Endorsed': symptom.replace('dsm_', '').replace('_met', ''),
                    'Frequency': symptom_freq[symptom],
                    'Proportion of Low Performers': symptom_prop[symptom],
                    'N Low Performers': n_low_performers
                })
                
    if not low_performer_symptoms:
        print("\n- No significant symptom patterns found for low cognitive performers (or insufficient data per test).")
        return
        
    # --- 4. Report and Save Findings ---
    results_df = pd.DataFrame(low_performer_symptoms)
    # Sort for better readability: by test/domain, then by proportion descending
    results_df.sort_values(by=[f'Cognitive {analysis_type} Score (Percentile < 25)', 'Proportion of Low Performers'], ascending=[True, False], inplace=True)
    
    print(f"\n--- Common Symptoms Among Low Cognitive Performers (<25th Percentile on {analysis_type} Scores) ---")
    # Display top N symptoms per test (e.g., top 5)
    top_n = 5
    print(f"(Showing top {top_n} most common symptoms per {analysis_type.lower()} score where N Low Performers >= {min_low_performers})")
    for score_name, group in results_df.groupby(f'Cognitive {analysis_type} Score (Percentile < 25)'):
        print(f"Cognitive {analysis_type}: {score_name} (N Low Performers = {group['N Low Performers'].iloc[0]})")
        print(group[['Symptom Endorsed', 'Proportion of Low Performers']].head(top_n).to_string(index=False))        
    save_descriptives(results_df, output_filename, f"Common Symptoms for Low Cognitive {analysis_type} Performers")

# --- End of Function Modification ---

# --- Add Function: Analyze Speed-Accuracy Tradeoff ---
def analyze_speed_accuracy_tradeoff(all_data):
    """Analyzes the relationship between reaction time and errors within subtests."""
    analysis_df = all_data.get('analysis_df', pd.DataFrame()).copy()
    
    if analysis_df.empty:
        print("- Skipping speed-accuracy analysis: Missing analysis_df data.")
        return

    # Section title printed in main now
    # print("\n--- Analyzing Speed-Accuracy Tradeoffs ---")
    
    # Define potential pairs of (Reaction Time Metric, Error Metric, Test Name Suffix)
    # Prioritize standard scores. Add more pairs as needed based on column names.
    # Note: Interpretation depends on metric (higher RT = slower, higher Error = worse)
    metric_pairs = [
        # FPCPT Part 1
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 1',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Omission Errors* - Part 1', 'FPCPT_P1_RT_vs_Omission'),
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 1',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Commission Errors* - Part 1', 'FPCPT_P1_RT_vs_Commission'),
        # FPCPT Part 2
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 2',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Omission Errors* - Part 2', 'FPCPT_P2_RT_vs_Omission'),
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 2',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Incorrect Responses* - Part 2', 'FPCPT_P2_RT_vs_Incorrect'), # Assuming Incorrect ~= Commission
        # FPCPT Part 3
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 3',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Omission Errors* - Part 3', 'FPCPT_P3_RT_vs_Omission'),
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 3',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Incorrect Responses* - Part 3', 'FPCPT_P3_RT_vs_Incorrect'),
        # FPCPT Part 4
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 4',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Omission Errors* - Part 4', 'FPCPT_P4_RT_vs_Omission'),
        ('standard_score_Four Part Continuous Performance Test (FPCPT)_Average Correct Reaction Time* - Part 4',
         'standard_score_Four Part Continuous Performance Test (FPCPT)_Incorrect Responses* - Part 4', 'FPCPT_P4_RT_vs_Incorrect'),
        # Stroop Test (Interference part)
        ('standard_score_Stroop Test (ST)_Color-Word Interference Time* - Part 3',
         'standard_score_Stroop Test (ST)_Stroop Commission Errors*', 'Stroop_P3_InterferenceRT_vs_Commission'), # More specific name
         # Stroop Test (Simple RT part)
        ('standard_score_Stroop Test (ST)_Simple Reaction Time*',
         'standard_score_Stroop Test (ST)_Stroop Commission Errors*', 'Stroop_SimpleRT_vs_Commission'), # Added this pair
        # Shifting Attention Test
        ('standard_score_Shifting Attention Test (SAT)_Correct Reaction Time*',
         'standard_score_Shifting Attention Test (SAT)_Errors*', 'SAT_RT_vs_Errors'),
        # Continuous Performance Test (if available)
        ('standard_score_Continuous Performance Test (CPT)_Average Correct Reaction Time*',
         'standard_score_Continuous Performance Test (CPT)_Commission Errors*', 'CPT_RT_vs_Commission')
    ]

    results = []
    plots_generated = []

    for rt_col, err_col, name_suffix in metric_pairs:
        # Check if both columns exist
        if rt_col not in analysis_df.columns or err_col not in analysis_df.columns:
            # print(f"- Skipping {name_suffix}: Columns not found ({rt_col} or {err_col})")
            continue

        # Prepare data: select columns and drop NaNs for this pair
        pair_df = analysis_df[[rt_col, err_col]].copy()
        pair_df[rt_col] = pd.to_numeric(pair_df[rt_col], errors='coerce')
        pair_df[err_col] = pd.to_numeric(pair_df[err_col], errors='coerce')
        pair_df.dropna(inplace=True)

        if pair_df.shape[0] < 5: # Need sufficient data points
            # print(f"- Skipping {name_suffix}: Insufficient data points ({pair_df.shape[0]})")
            continue

        # Calculate Spearman Correlation
        try:
            # Check for constant input which throws error in spearmanr
            if pair_df[rt_col].nunique() <= 1 or pair_df[err_col].nunique() <= 1:
                 corr, p_value = np.nan, np.nan
                 # print(f"- Skipping correlation for {name_suffix}: Constant input detected.")
            else:
                 corr, p_value = stats.spearmanr(pair_df[rt_col], pair_df[err_col])
        except Exception as e:
            print(f"- Error calculating correlation for {name_suffix}: {e}")
            corr, p_value = np.nan, np.nan

        results.append({
            'Test Pair Suffix': name_suffix,
            'Reaction Time Metric': rt_col,
            'Error Metric': err_col,
            'Spearman R': corr,
            'P-value': p_value,
            'N': pair_df.shape[0]
        })

        # Generate Scatter Plot if correlation is calculable
        if pd.notna(corr):
            try:
                plt.figure(figsize=(8, 6))
                sns.scatterplot(data=pair_df, x=rt_col, y=err_col)
                # Add regression line to visualize trend
                sns.regplot(data=pair_df, x=rt_col, y=err_col, scatter=False, ci=None, line_kws={"color": "red"})
                
                # Cleaned labels for plot
                rt_label = rt_col.replace('standard_score_', '').replace('percentile_', '')
                err_label = err_col.replace('standard_score_', '').replace('percentile_', '')
                # Add interpretation hints based on metric type (* implies lower is better for RT, higher for Error)
                rt_interp = "(Lower=Faster?)" if '*' in rt_col else "(Higher=Faster?)"
                err_interp = "(Higher=More Err?)" if '*' in err_col else "(Lower=More Err?)"
                
                plt.title(f"Speed vs. Accuracy: {name_suffix}\nSpearman R={corr:.2f}, p={p_value:.3f}, N={pair_df.shape[0]}")
                plt.xlabel(f"{rt_label}\n{rt_interp}")
                plt.ylabel(f"{err_label}\n{err_interp}")
                plt.tight_layout()
                plot_filename = os.path.join(PLOTS_DIR, f"speed_accuracy_{name_suffix}.png")
                plt.savefig(plot_filename, bbox_inches='tight')
                plt.close()
                plots_generated.append(plot_filename)
            except Exception as e:
                print(f"- Error generating plot for {name_suffix}: {e}")

    if not results:
        print("- No suitable data found for speed-accuracy analysis.")
        return

    results_df = pd.DataFrame(results)
    significant_results = results_df[results_df['P-value'] < 0.05].sort_values(by='P-value')

    print("\nSignificant Speed-Accuracy Correlations (Spearman p < 0.05):")
    if not significant_results.empty:
        # Added metric names for clarity
        print(significant_results[['Test Pair Suffix', 'Spearman R', 'P-value', 'N', 'Reaction Time Metric', 'Error Metric']].to_string(index=False))
    else:
        print("- None found.")
        
    print(f"\nGenerated {len(plots_generated)} speed-accuracy scatter plots in: {PLOTS_DIR}")
    # Save all results, not just significant
    save_descriptives(results_df, "speed_accuracy_correlations.csv", "Speed-Accuracy Correlations (All Pairs)")

# --- End of Added Function ---

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting ADHD Data Analysis...")
    
    conn = connect_db(DB_PATH)
    
    if conn:
        # Load all data into a dictionary of DataFrames
        all_data = load_data(conn)
        conn.close() # Close connection after loading data
        print("Database connection closed.")

        # Check if essential dataframes are loaded
        patients_df = all_data.get('patients', pd.DataFrame())
        diagnosis_df = all_data.get('asrs_dsm_diagnosis', pd.DataFrame())
        criteria_df = all_data.get('dsm_criteria_met', pd.DataFrame())
        cognitive_subtests_df = all_data.get('subtest_results', pd.DataFrame()) # Corrected key
        npq_scores_df = all_data.get('npq_scores', pd.DataFrame())
        analysis_df = all_data.get('analysis_df', pd.DataFrame()) # The merged df

        if not analysis_df.empty:
            print(f"\nProceeding with analysis on {len(analysis_df)} patients.")
            
            # --- Run Foundational Analyses ---
            analyze_demographics(patients_df) # Use raw patients table for age
            analyze_adhd_subtypes(diagnosis_df) # Use raw diagnosis table
            
            # Use the merged analysis_df for cognitive analysis as it's pivoted
            analyze_cognitive_performance(analysis_df) 
            
            # Use raw tables for symptom analysis
            analyze_adhd_symptoms(diagnosis_df, criteria_df) 
            
            analyze_npq_comorbidity(npq_scores_df) # Use raw npq table
            
            analyze_cognitive_by_subtype(all_data)
            
            # --- Add Analysis: Correlation between Symptoms and Cognition ---
            print("\n--- Analyzing Correlation between ADHD Symptoms and Cognitive Performance ---")
            analyze_symptom_cognition_correlation(all_data)
            # --- End of Added Analysis ---
            
            # --- Add Analysis: Symptoms of Low Cognitive Performers ---
            print("\n--- Analyzing Symptom Profile of Low Cognitive Performers (Subtests) ---")
            analyze_low_cognition_symptoms(all_data, analyze_domains=False) # Use the same all_data dict
            print("\n--- Analyzing Symptom Profile of Low Cognitive Performers (Domains) ---")
            analyze_low_cognition_symptoms(all_data, analyze_domains=True) # Run again for domains
            # --- End of Added Analysis ---
            
            # --- Add Analysis: Speed-Accuracy Tradeoff ---
            print("\n--- Analyzing Speed-Accuracy Tradeoffs ---")
            analyze_speed_accuracy_tradeoff(all_data)
            # --- End of Added Analysis ---

            print("\n--- Analysis Script Finished ---")
            print(f"Outputs saved in: {OUTPUT_DIR}")
            print(f"Plots saved in: {PLOTS_DIR}")
            
        else:
             print("\nEssential data (patients) could not be loaded or merged. Analysis cannot proceed.")
             
    else:
        print("Database connection failed. Exiting.")

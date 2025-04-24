#!/usr/bin/env python3
"""
ADHD Cognitive Domain Analysis

This script analyzes relationships between cognitive domain scores and ADHD symptoms
from the cognitive_analysis database. It explores correlations between:
1. Cognitive domains and specific ASRS symptoms
2. Cognitive domains and ADHD categories (Inattentive, Hyperactive, Combined)
3. Identifies patterns while excluding invalid data

Usage:
    python adhd_cognitive_analysis.py [--visualize] [--export]

Options:
    --visualize    Generate visualizations of the relationships
    --export       Export results to CSV files
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path
import argparse

# Add parent directory to path so we can import modules from there
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
sys.path.append(str(parent_dir))

# Import ASRS-DSM mapping for analysis
try:
    from asrs_dsm_mapper import asrs_to_dsm5_a, asrs_to_dsm5_b
except ImportError:
    print("Warning: Could not import ASRS-DSM mapping, some analyses will be limited")
    asrs_to_dsm5_a = {}
    asrs_to_dsm5_b = {}

# Define paths
DB_PATH = os.path.join(script_dir, "cognitive_analysis.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(parent_dir, "cognitive_analysis.db")

# Check if database exists
if not os.path.exists(DB_PATH):
    print(f"Error: Database not found at {DB_PATH}")
    print("Please ensure the database exists or update the DB_PATH variable.")
    sys.exit(1)

# Define ADHD symptom categories based on DSM-5
DSM_CATEGORIES = {
    'Inattentive': [f'1{chr(ord("a") + i)}' for i in range(9)],  # 1a through 1i
    'Hyperactive-Impulsive': [f'2{chr(ord("a") + i)}' for i in range(9)],  # 2a through 2i
}

# Map cognitive domains to potentially related DSM-5 ADHD symptoms
DOMAIN_TO_DSM_MAP = {
    'Composite Memory': ['1i', '1g'],
    'Verbal Memory': ['1i'],
    'Visual Memory': ['1i', '1g'],
    'Psychomotor Speed': ['1d', '2e'],
    'Reaction Time': ['2g', '2h'],
    'Complex Attention': ['1b', '1h'],
    'Cognitive Flexibility': ['1d', '1e'],
    'Processing Speed': ['1a', '1b', '1d'],
    'Executive Function': ['1d', '1e', '1f', '1h', '2a', '2b', '2c', '2d', '2e', '2f', '2g', '2h', '2i'],
    'Simple Attention': ['1b', '1c', '1h'],
    'Motor Speed': ['2a', '2e'],
    'Social Acuity': ['2i'],
    'Reasoning': ['1e', '1d'],
    'Sustained Attention': ['1a', '1b', '1c', '1f', '1h'],
    'Working Memory': ['1c', '1d', '1e', '1g', '1i', '2g'],
    'Neurocognition Index (NCI)': []  # General measure, no specific mapping
}

class ADHDCognitiveAnalysis:
    """Main class for analyzing relationships between cognitive domains and ADHD symptoms."""
    
    def __init__(self, db_path=DB_PATH):
        """Initialize the analysis with the database path."""
        self.db_path = db_path
        self.conn = None
        self.cognitive_data = None
        self.asrs_data = None
        self.patient_data = None
        self.correlation_results = {}
        self.visualize = False
        self.output_dir = script_dir / 'results'
        self.output_dir.mkdir(exist_ok=True)
        
    def connect_to_db(self):
        """Connect to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"Connected to database: {self.db_path}")
            return True
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return False
    
    def load_data(self):
        """Load all required data from the database."""
        if not self.conn:
            if not self.connect_to_db():
                return False
        
        # Load cognitive scores (excluding invalid data)
        query = """
        SELECT 
            cs.patient_id, 
            cs.domain, 
            cs.standard_score AS score, 
            cs.percentile,
            cs.validity_index,
            ad.adhd_diagnosis,
            ad.adhd_type,
            ad.inattentive_met,
            ad.hyperactive_met
        FROM 
            cognitive_scores cs
        JOIN
            patients p ON cs.patient_id = p.patient_id
        LEFT JOIN
            adhd_diagnoses ad ON cs.patient_id = ad.patient_id
        WHERE
            cs.validity_index = 'Yes' OR cs.validity_index IS NULL
        """
        
        self.cognitive_data = pd.read_sql(query, self.conn)
        print(f"Loaded {len(self.cognitive_data)} valid cognitive scores")

        # Load DSM-5 criteria data
        query = """
        SELECT 
            dc.patient_id,
            dc.criterion_id,
            dc.criterion_met,
            dc.asrs_question,
            dc.asrs_response
        FROM 
            dsm5_criteria dc
        JOIN
            patients p ON dc.patient_id = p.patient_id
        """
        
        self.dsm_criteria = pd.read_sql(query, self.conn)
        print(f"Loaded {len(self.dsm_criteria)} DSM-5 criteria records")
        
        # Create pivot table for DSM-5 criteria
        self.dsm_pivot = self.dsm_criteria.pivot_table(
            index='patient_id',
            columns='criterion_id',
            values='criterion_met',
            aggfunc='first'
        ).fillna(False)

        return len(self.cognitive_data) > 0 and len(self.dsm_criteria) > 0

    def analyze_domain_dsm_correlations(self):
        """Analyze correlations between cognitive domains and DSM-5 criteria."""
        if self.cognitive_data is None or self.dsm_pivot is None:
            print("Required data not loaded")
            return False

        # Prepare cognitive data
        cognitive_pivot = self.cognitive_data.pivot_table(
            index='patient_id',
            columns='domain',
            values='score',
            aggfunc='first'
        )
        print(f"\nFound cognitive domains: {list(cognitive_pivot.columns)}")

        # Ensure patient IDs match between datasets
        common_patients = set(cognitive_pivot.index) & set(self.dsm_pivot.index)
        cognitive_pivot = cognitive_pivot.loc[list(common_patients)]
        dsm_pivot = self.dsm_pivot.loc[list(common_patients)]
        print(f"Found {len(common_patients)} patients with both cognitive and DSM-5 data")
        print(f"DSM-5 criteria found: {list(dsm_pivot.columns)}")

        correlations = {}
        p_values = {}

        # Analyze each cognitive domain
        for domain in cognitive_pivot.columns:
            print(f"\nAnalyzing domain: {domain}")
            domain_scores = cognitive_pivot[domain]
            domain_correlations = {}
            domain_p_values = {}

            # Analyze correlation with each DSM criterion
            for criterion in dsm_pivot.columns:
                criterion_met = dsm_pivot[criterion]
                
                # Ensure we have matching data points
                valid_mask = ~domain_scores.isna() & ~criterion_met.isna()
                valid_count = valid_mask.sum()
                print(f"Found {valid_count} valid data points for {criterion}")
                
                if valid_count < 2:
                    print("Warning: Not enough valid data points")
                    continue

                # Calculate point-biserial correlation
                correlation, p_value = stats.pointbiserialr(
                    domain_scores[valid_mask].astype(float),
                    criterion_met[valid_mask].astype(int)
                )

                if not np.isnan(correlation):
                    domain_correlations[criterion] = correlation
                    domain_p_values[criterion] = p_value
                    print(f"Correlation with {criterion}: r={correlation:.3f}, p={p_value:.3f}")

            correlations[domain] = domain_correlations
            p_values[domain] = domain_p_values

        self.correlation_results = {
            'correlations': correlations,
            'p_values': p_values
        }

        return True

    def analyze_domain_adhd_type_differences(self):
        """Analyze cognitive differences between ADHD types."""
        if self.cognitive_data is None:
            print("Required data not loaded")
            return False

        results = {}
        
        for domain in DOMAIN_TO_DSM_MAP.keys():
            print(f"\nAnalyzing {domain}")
            domain_data = self.cognitive_data[self.cognitive_data['domain'] == domain]
            if len(domain_data) == 0:
                print("No data found for domain")
                continue

            # Prepare data for each ADHD type
            no_adhd = domain_data[domain_data['adhd_diagnosis'].fillna(0) == 0]['score'].dropna()
            inattentive = domain_data[domain_data['adhd_type'] == 'Inattentive']['score'].dropna()
            hyperactive = domain_data[domain_data['adhd_type'] == 'Hyperactive']['score'].dropna()
            combined = domain_data[domain_data['adhd_type'] == 'Combined']['score'].dropna()

            print(f"Sample sizes:")
            print(f"No ADHD: {len(no_adhd)}")
            print(f"Inattentive: {len(inattentive)}")
            print(f"Hyperactive: {len(hyperactive)}")
            print(f"Combined: {len(combined)}")

            # Perform Kruskal-Wallis H-test
            groups = [g for g in [no_adhd, inattentive, hyperactive, combined] if len(g) > 0]
            if len(groups) > 1:
                h_stat, p_value = stats.kruskal(*groups)
                print(f"Kruskal-Wallis test: H={h_stat:.3f}, p={p_value:.3f}")
                
                results[domain] = {
                    'h_statistic': h_stat,
                    'p_value': p_value,
                    'group_means': {
                        'No ADHD': no_adhd.mean() if len(no_adhd) > 0 else None,
                        'Inattentive': inattentive.mean() if len(inattentive) > 0 else None,
                        'Hyperactive': hyperactive.mean() if len(hyperactive) > 0 else None,
                        'Combined': combined.mean() if len(combined) > 0 else None
                    }
                }

        self.adhd_type_results = results
        return True

    def analyze_top_correlations(self):
        """Find the top 4 strongest correlations for radar chart domains."""
        if not hasattr(self, 'correlation_results'):
            print("No correlation results available")
            return

        radar_domains = [
            'Verbal Memory', 'Visual Memory', 'Executive Function',
            'Processing Speed', 'Cognitive Flexibility', 'Complex Attention',
            'Reaction Time', 'Psychomotor Speed'
        ]

        print("\nTop 4 Strongest Correlations by Domain:")
        print("=" * 50)

        for domain in radar_domains:
            if domain not in self.correlation_results['correlations']:
                print(f"\n{domain}: No data available")
                continue

            correlations = self.correlation_results['correlations'][domain]
            p_values = self.correlation_results['p_values'][domain]
            
            # Convert to list of (criterion, correlation, p_value) tuples
            corr_list = [(crit, corr, p_values[crit]) 
                        for crit, corr in correlations.items()]
            
            # Sort by absolute correlation value
            corr_list.sort(key=lambda x: abs(x[1]), reverse=True)
            
            print(f"\n{domain}:")
            print("-" * 30)
            for i, (criterion, corr, p) in enumerate(corr_list[:4]):
                sig = "*" if p < 0.05 else ""
                print(f"{i+1}. {criterion}: r={corr:.3f}, p={p:.3f}{sig}")

    def generate_visualizations(self):
        """Generate visualizations of the analysis results."""
        if not self.visualize:
            return

        # Set up the style
        plt.style.use('seaborn-v0_8-whitegrid')
        
        # 1. Correlation heatmap
        if self.correlation_results:
            correlations = self.correlation_results['correlations']
            
            # Prepare correlation matrix
            domains = list(correlations.keys())
            all_criteria = sorted(set(crit for d in correlations.values() for crit in d.keys()))
            
            corr_matrix = np.zeros((len(domains), len(all_criteria)))
            for i, domain in enumerate(domains):
                for j, criterion in enumerate(all_criteria):
                    corr_matrix[i, j] = correlations[domain].get(criterion, 0)
            
            plt.figure(figsize=(15, 10))
            sns.heatmap(
                corr_matrix,
                xticklabels=all_criteria,
                yticklabels=domains,
                cmap='RdBu_r',
                center=0,
                annot=True,
                fmt='.2f'
            )
            plt.title('Cognitive Domain - DSM-5 Criteria Correlations')
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, 'domain_dsm_correlations.png'))
            plt.close()

        # 2. ADHD Type Comparisons
        if hasattr(self, 'adhd_type_results'):
            for domain, results in self.adhd_type_results.items():
                plt.figure(figsize=(10, 6))
                means = results['group_means']
                groups = list(means.keys())
                values = [v for v in means.values() if v is not None]
                
                if values:  # Only plot if we have values
                    plt.bar(
                        [g for g, v in means.items() if v is not None],
                        values
                    )
                    plt.title(f'{domain} Scores by ADHD Type\np={results["p_value"]:.3f}')
                    plt.ylabel('Standard Score')
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    plt.savefig(os.path.join(self.output_dir, f'{domain.lower().replace(" ", "_")}_adhd_types.png'))
                plt.close()

    def export_results(self):
        """Export analysis results to CSV files."""
        # Export correlation results
        if self.correlation_results:
            correlations_df = pd.DataFrame(self.correlation_results['correlations']).T
            p_values_df = pd.DataFrame(self.correlation_results['p_values']).T
            
            correlations_df.to_csv(os.path.join(self.output_dir, 'domain_dsm_correlations.csv'))
            p_values_df.to_csv(os.path.join(self.output_dir, 'domain_dsm_pvalues.csv'))

        # Export ADHD type comparison results
        if hasattr(self, 'adhd_type_results'):
            type_results = []
            for domain, results in self.adhd_type_results.items():
                row = {
                    'Domain': domain,
                    'H_Statistic': results['h_statistic'],
                    'P_Value': results['p_value']
                }
                row.update({f'Mean_{k}': v for k, v in results['group_means'].items()})
                type_results.append(row)
            
            pd.DataFrame(type_results).to_csv(
                os.path.join(self.output_dir, 'adhd_type_comparisons.csv'),
                index=False
            )
    
    def run_analysis(self, visualize=False, export=False):
        """Run the complete analysis pipeline."""
        self.visualize = visualize
        
        print("\n" + "="*50)
        print("ADHD Cognitive Domain Analysis")
        print("="*50)
        
        if not self.connect_to_db():
            print("Failed to connect to database, analysis aborted")
            return False
        
        if not self.load_data():
            print("Failed to load data, analysis aborted")
            return False
        
        # Run analyses
        print("\n" + "-"*50)
        print("Running Analyses")
        print("-"*50)
        
        self.analyze_domain_dsm_correlations()
        self.analyze_domain_adhd_type_differences()
        self.analyze_top_correlations()
        
        # Visualize and export results
        if visualize:
            print("\n" + "-"*50)
            print("Generating Visualizations")
            print("-"*50)
            self.generate_visualizations()
        
        if export:
            print("\n" + "-"*50)
            print("Exporting Results")
            print("-"*50)
            self.export_results()
        
        print("\n" + "="*50)
        print("Analysis Complete")
        print("="*50)
        
        return True


def main():
    """Main function to run the analysis."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ADHD Cognitive Domain Analysis')
    parser.add_argument('--visualize', action='store_true', help='Generate visualizations')
    parser.add_argument('--export', action='store_true', help='Export results to CSV')
    args = parser.parse_args()
    
    # Run the analysis
    analyzer = ADHDCognitiveAnalysis()
    analyzer.run_analysis(visualize=args.visualize, export=args.export)


if __name__ == "__main__":
    main()

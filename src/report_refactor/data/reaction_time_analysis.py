#!/usr/bin/env python3
"""
Reaction Time and Error Analysis

This script analyzes reaction time data and error rates from cognitive tests,
focusing on the relationship between reaction time, accuracy, and errors.
It creates visualizations to help understand these relationships.

Usage:
    python reaction_time_analysis.py [--visualize] [--export]

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

# Define paths
DB_PATH = os.path.join(script_dir, "cognitive_analysis.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(parent_dir, "cognitive_analysis.db")

# Check if database exists
if not os.path.exists(DB_PATH):
    print(f"Error: Database not found at {DB_PATH}")
    print("Please ensure the database exists or update the DB_PATH variable.")
    sys.exit(1)

# Define tests with reaction time components
REACTION_TIME_TESTS = [
    'Reaction Time',
    'Stroop Test',
    'Shifting Attention Test',
    'Continuous Performance Test'
]

# Define tests with error counts
ERROR_TESTS = [
    'Symbol Digit Coding',
    'Stroop Test',
    'Continuous Performance Test',
    'Shifting Attention Test'
]

class ReactionTimeAnalysis:
    """Analysis class for reaction time and error data."""
    
    def __init__(self, db_path=DB_PATH):
        """Initialize the analysis with the database path."""
        self.db_path = db_path
        self.conn = None
        self.subtest_data = None
        self.cognitive_data = None
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
        
        # Load subtest results for reaction time and error analysis
        query = """
        SELECT 
            sr.patient_id, 
            sr.subtest_name, 
            sr.metric, 
            sr.score,
            sr.standard_score,
            sr.percentile
        FROM 
            subtest_results sr
        JOIN
            patients p ON sr.patient_id = p.patient_id
        WHERE
            sr.subtest_name IN (?, ?, ?, ?, ?)
        """
        
        # Combine all relevant tests
        all_tests = list(set(REACTION_TIME_TESTS + ERROR_TESTS))
        
        self.subtest_data = pd.read_sql(query, self.conn, params=all_tests + [''])
        print(f"Loaded {len(self.subtest_data)} subtest results")

        # Load cognitive domain scores for correlation analysis
        query = """
        SELECT 
            cs.patient_id, 
            cs.domain, 
            cs.standard_score AS score, 
            cs.percentile,
            cs.validity_index
        FROM 
            cognitive_scores cs
        JOIN
            patients p ON cs.patient_id = p.patient_id
        WHERE
            cs.validity_index = 'Yes' OR cs.validity_index IS NULL
        """
        
        self.cognitive_data = pd.read_sql(query, self.conn)
        print(f"Loaded {len(self.cognitive_data)} cognitive domain scores")
        
        return len(self.subtest_data) > 0
    
    def prepare_reaction_time_data(self):
        """Prepare reaction time data for analysis."""
        if self.subtest_data is None:
            print("No subtest data loaded")
            return False
        
        # Filter for reaction time related metrics
        rt_data = self.subtest_data[
            (self.subtest_data['subtest_name'].isin(REACTION_TIME_TESTS)) & 
            (self.subtest_data['metric'].str.contains('Reaction Time|RT|Response Time|Milliseconds|msec', 
                                                     case=False, na=False))
        ]
        
        # Create a pivot table with patients as rows and tests/metrics as columns
        rt_pivot = rt_data.pivot_table(
            index='patient_id',
            columns=['subtest_name', 'metric'],
            values='score'
        )
        
        # Flatten column names
        rt_pivot.columns = [f"{test}_{metric}" for test, metric in rt_pivot.columns]
        
        self.rt_data = rt_data
        self.rt_pivot = rt_pivot
        
        print(f"Prepared reaction time data for {len(rt_pivot)} patients")
        return True
    
    def prepare_error_data(self):
        """Prepare error data for analysis."""
        if self.subtest_data is None:
            print("No subtest data loaded")
            return False
        
        # Filter for error related metrics
        error_data = self.subtest_data[
            (self.subtest_data['subtest_name'].isin(ERROR_TESTS)) & 
            (self.subtest_data['metric'].str.contains('Error|Incorrect|Wrong|Miss|False', 
                                                    case=False, na=False))
        ]
        
        # Create a pivot table with patients as rows and tests/metrics as columns
        error_pivot = error_data.pivot_table(
            index='patient_id',
            columns=['subtest_name', 'metric'],
            values='score'
        )
        
        # Flatten column names
        error_pivot.columns = [f"{test}_{metric}" for test, metric in error_pivot.columns]
        
        self.error_data = error_data
        self.error_pivot = error_pivot
        
        print(f"Prepared error data for {len(error_pivot)} patients")
        return True
    
    def prepare_accuracy_data(self):
        """Prepare accuracy data for analysis."""
        if self.subtest_data is None:
            print("No subtest data loaded")
            return False
        
        # Filter for accuracy related metrics
        accuracy_data = self.subtest_data[
            (self.subtest_data['subtest_name'].isin(ERROR_TESTS + REACTION_TIME_TESTS)) & 
            (self.subtest_data['metric'].str.contains('Correct|Accuracy|Right|Hit', 
                                                    case=False, na=False))
        ]
        
        # Create a pivot table with patients as rows and tests/metrics as columns
        accuracy_pivot = accuracy_data.pivot_table(
            index='patient_id',
            columns=['subtest_name', 'metric'],
            values='score'
        )
        
        # Flatten column names
        accuracy_pivot.columns = [f"{test}_{metric}" for test, metric in accuracy_pivot.columns]
        
        self.accuracy_data = accuracy_data
        self.accuracy_pivot = accuracy_pivot
        
        print(f"Prepared accuracy data for {len(accuracy_pivot)} patients")
        return True
    
    def merge_analysis_data(self):
        """Merge all data for analysis."""
        # Initialize with the first dataset
        if hasattr(self, 'rt_pivot'):
            merged_data = self.rt_pivot.copy()
        elif hasattr(self, 'error_pivot'):
            merged_data = self.error_pivot.copy()
        elif hasattr(self, 'accuracy_pivot'):
            merged_data = self.accuracy_pivot.copy()
        else:
            print("No data prepared for merging")
            return False
        
        # Add other datasets if they exist
        if hasattr(self, 'rt_pivot') and id(merged_data) != id(self.rt_pivot):
            merged_data = pd.merge(
                merged_data, self.rt_pivot,
                left_index=True, right_index=True,
                how='outer'
            )
        
        if hasattr(self, 'error_pivot'):
            merged_data = pd.merge(
                merged_data, self.error_pivot,
                left_index=True, right_index=True,
                how='outer'
            )
        
        if hasattr(self, 'accuracy_pivot'):
            merged_data = pd.merge(
                merged_data, self.accuracy_pivot,
                left_index=True, right_index=True,
                how='outer'
            )
            
        # Reshape cognitive data for merging
        if hasattr(self, 'cognitive_data'):
            cognitive_pivot = self.cognitive_data.pivot_table(
                index='patient_id',
                columns='domain',
                values='score'
            )
            
            merged_data = pd.merge(
                merged_data, cognitive_pivot,
                left_index=True, right_index=True,
                how='outer'
            )
        
        self.analysis_data = merged_data
        print(f"Merged analysis data for {len(merged_data)} patients with {merged_data.shape[1]} variables")
        return True
    
    def analyze_rt_accuracy_relationship(self):
        """Analyze the relationship between reaction time and accuracy."""
        if not hasattr(self, 'analysis_data'):
            print("No analysis data available")
            return False
        
        results = []
        
        # Find pairs of reaction time and accuracy metrics for the same test
        for rt_col in self.analysis_data.columns:
            if not any(test in rt_col for test in REACTION_TIME_TESTS):
                continue
            if not any(term in rt_col.lower() for term in ['reaction', 'rt', 'response time', 'millisecond', 'msec']):
                continue
            
            test_name = rt_col.split('_')[0] 
            
            # Look for corresponding accuracy metrics
            for acc_col in self.analysis_data.columns:
                if test_name not in acc_col:
                    continue
                if not any(term in acc_col.lower() for term in ['correct', 'accuracy', 'right', 'hit']):
                    continue
                
                # Skip if either column has no valid data
                if self.analysis_data[rt_col].isna().all() or self.analysis_data[acc_col].isna().all():
                    continue
                
                # Calculate correlation
                valid_data = self.analysis_data[[rt_col, acc_col]].dropna()
                
                if len(valid_data) < 5:  # Need at least 5 data points for meaningful correlation
                    continue
                
                r, p = stats.pearsonr(valid_data[rt_col], valid_data[acc_col])
                
                results.append({
                    'Test': test_name,
                    'RT_Metric': rt_col,
                    'Accuracy_Metric': acc_col,
                    'Correlation': r,
                    'P_Value': p,
                    'Significant': p < 0.05,
                    'Sample_Size': len(valid_data)
                })
        
        self.rt_accuracy_correlations = pd.DataFrame(results)
        
        if not self.rt_accuracy_correlations.empty:
            print("\nReaction Time vs Accuracy Correlations:")
            for _, row in self.rt_accuracy_correlations.iterrows():
                sig = "significant" if row['Significant'] else "non-significant"
                print(f"{row['Test']}: r={row['Correlation']:.2f}, p={row['P_Value']:.3f} ({sig}, n={row['Sample_Size']})")
        
        return len(results) > 0
    
    def analyze_error_patterns(self):
        """Analyze patterns in error rates across tests."""
        if not hasattr(self, 'analysis_data') or not hasattr(self, 'error_pivot'):
            print("No error data available")
            return False
        
        # Calculate correlations between error metrics
        error_cols = [col for col in self.analysis_data.columns 
                     if any(test in col for test in ERROR_TESTS) and
                     any(term in col.lower() for term in ['error', 'incorrect', 'wrong', 'miss', 'false'])]
        
        if len(error_cols) < 2:
            print("Not enough error metrics for correlation analysis")
            return False
        
        # Calculate correlation matrix
        error_corr = self.analysis_data[error_cols].corr(method='pearson')
        
        # Extract significant correlations
        corr_results = []
        for i in range(len(error_cols)):
            for j in range(i+1, len(error_cols)):
                col1 = error_cols[i]
                col2 = error_cols[j]
                
                # Skip if either column has no valid data
                if self.analysis_data[col1].isna().all() or self.analysis_data[col2].isna().all():
                    continue
                
                # Calculate correlation with p-value
                valid_data = self.analysis_data[[col1, col2]].dropna()
                
                if len(valid_data) < 5:  # Need at least 5 data points
                    continue
                
                r, p = stats.pearsonr(valid_data[col1], valid_data[col2])
                
                corr_results.append({
                    'Metric1': col1,
                    'Metric2': col2,
                    'Correlation': r,
                    'P_Value': p,
                    'Significant': p < 0.05,
                    'Sample_Size': len(valid_data)
                })
        
        self.error_correlations = pd.DataFrame(corr_results)
        self.error_corr_matrix = error_corr
        
        if not self.error_correlations.empty:
            print("\nError Metric Correlations:")
            sig_corrs = self.error_correlations[self.error_correlations['Significant']]
            for _, row in sig_corrs.iterrows():
                print(f"{row['Metric1']} & {row['Metric2']}: r={row['Correlation']:.2f}, p={row['P_Value']:.3f} (n={row['Sample_Size']})")
        
        return True
    
    def analyze_cognitive_domain_relationships(self):
        """Analyze relationships between cognitive domains and reaction time/errors."""
        if not hasattr(self, 'analysis_data'):
            print("No analysis data available")
            return False
        
        # Identify cognitive domain columns
        domain_cols = [col for col in self.analysis_data.columns 
                     if col in ['Neurocognition Index (NCI)', 'Composite Memory', 'Reaction Time', 
                                'Complex Attention', 'Cognitive Flexibility', 'Processing Speed',
                                'Executive Function', 'Simple Attention', 'Motor Speed']]
        
        # Identify RT and error columns
        rt_cols = [col for col in self.analysis_data.columns 
                  if any(test in col for test in REACTION_TIME_TESTS) and
                  any(term in col.lower() for term in ['reaction', 'rt', 'response time', 'millisecond', 'msec'])]
        
        error_cols = [col for col in self.analysis_data.columns 
                     if any(test in col for test in ERROR_TESTS) and
                     any(term in col.lower() for term in ['error', 'incorrect', 'wrong', 'miss', 'false'])]
        
        results = []
        
        # Analyze correlations between domains and RT/errors
        for domain in domain_cols:
            # Correlations with reaction times
            for rt_col in rt_cols:
                # Skip if either column has no valid data
                if self.analysis_data[domain].isna().all() or self.analysis_data[rt_col].isna().all():
                    continue
                
                # Calculate correlation
                valid_data = self.analysis_data[[domain, rt_col]].dropna()
                
                if len(valid_data) < 5:  # Need at least 5 data points
                    continue
                
                r, p = stats.pearsonr(valid_data[domain], valid_data[rt_col])
                
                results.append({
                    'Domain': domain,
                    'Metric': rt_col,
                    'Metric_Type': 'Reaction Time',
                    'Correlation': r,
                    'P_Value': p,
                    'Significant': p < 0.05,
                    'Sample_Size': len(valid_data)
                })
            
            # Correlations with errors
            for error_col in error_cols:
                # Skip if either column has no valid data
                if self.analysis_data[domain].isna().all() or self.analysis_data[error_col].isna().all():
                    continue
                
                # Calculate correlation
                valid_data = self.analysis_data[[domain, error_col]].dropna()
                
                if len(valid_data) < 5:  # Need at least 5 data points
                    continue
                
                r, p = stats.pearsonr(valid_data[domain], valid_data[error_col])
                
                results.append({
                    'Domain': domain,
                    'Metric': error_col,
                    'Metric_Type': 'Error',
                    'Correlation': r,
                    'P_Value': p,
                    'Significant': p < 0.05,
                    'Sample_Size': len(valid_data)
                })
        
        self.domain_correlations = pd.DataFrame(results)
        
        if not self.domain_correlations.empty:
            print("\nCognitive Domain Correlations with RT/Errors:")
            sig_corrs = self.domain_correlations[self.domain_correlations['Significant']]
            for _, row in sig_corrs.iterrows():
                print(f"{row['Domain']} & {row['Metric']} ({row['Metric_Type']}): " +
                      f"r={row['Correlation']:.2f}, p={row['P_Value']:.3f} (n={row['Sample_Size']})")
        
        return True
    
    def visualize_results(self, visualize=False):
        """Create visualizations of the analysis results."""
        if not visualize:
            return
        
        plt.style.use('seaborn-v0_8-whitegrid')
        
        # Create results directory if it doesn't exist
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True)
        
        # 1. Reaction Time vs Accuracy Scatter Plots
        if hasattr(self, 'rt_accuracy_correlations') and not self.rt_accuracy_correlations.empty:
            for _, row in self.rt_accuracy_correlations.iterrows():
                plt.figure(figsize=(10, 6))
                
                # Get the data
                rt_col = row['RT_Metric']
                acc_col = row['Accuracy_Metric']
                
                # Create scatter plot with trend line
                sns.regplot(
                    x=rt_col, 
                    y=acc_col, 
                    data=self.analysis_data,
                    scatter_kws={'alpha': 0.6},
                    line_kws={'color': 'red'}
                )
                
                # Add correlation coefficient to title
                plt.title(f"{row['Test']}: Reaction Time vs Accuracy\nr={row['Correlation']:.2f}, p={row['P_Value']:.3f}")
                plt.xlabel(f"Reaction Time ({rt_col})")
                plt.ylabel(f"Accuracy ({acc_col})")
                
                # Add annotation about lower RT being better
                plt.annotate(
                    "Lower reaction times are better",
                    xy=(0.05, 0.05),
                    xycoords='axes fraction',
                    bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.3)
                )
                
                plt.tight_layout()
                plt.savefig(os.path.join(self.output_dir, f"{row['Test'].replace(' ', '_')}_RT_vs_Accuracy.png"))
                plt.close()
                
                print(f"Saved visualization: {row['Test'].replace(' ', '_')}_RT_vs_Accuracy.png")
        
        # 2. Error Correlation Heatmap
        if hasattr(self, 'error_corr_matrix'):
            plt.figure(figsize=(12, 10))
            sns.heatmap(
                self.error_corr_matrix, 
                annot=True, 
                cmap='coolwarm', 
                center=0,
                fmt='.2f'
            )
            plt.title('Correlations Between Error Metrics')
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, 'error_correlation_matrix.png'))
            plt.close()
            print(f"Saved visualization: error_correlation_matrix.png")
        
        # 3. Domain-RT/Error Correlation Plots
        if hasattr(self, 'domain_correlations') and not self.domain_correlations.empty:
            # Group by domain for visualization
            for domain in self.domain_correlations['Domain'].unique():
                domain_data = self.domain_correlations[self.domain_correlations['Domain'] == domain]
                
                if domain_data['Significant'].any():
                    plt.figure(figsize=(12, 6))
                    
                    # Create bar plot of correlations
                    sns.barplot(
                        x='Metric', 
                        y='Correlation',
                        hue='Metric_Type',
                        data=domain_data[domain_data['Significant']],
                        palette={'Reaction Time': 'blue', 'Error': 'red'}
                    )
                    
                    plt.title(f'{domain}: Significant Correlations with RT/Errors')
                    plt.xticks(rotation=90)
                    plt.tight_layout()
                    plt.savefig(os.path.join(self.output_dir, f"{domain.replace(' ', '_')}_RT_Error_Correlations.png"))
                    plt.close()
                    
                    print(f"Saved visualization: {domain.replace(' ', '_')}_RT_Error_Correlations.png")
        
        # 4. Combined RT and Error Analysis
        if hasattr(self, 'analysis_data'):
            # For each test that has both RT and error data, create a scatter plot
            for test in set(REACTION_TIME_TESTS).intersection(ERROR_TESTS):
                # Find RT and error columns for this test
                rt_cols = [col for col in self.analysis_data.columns if test in col and 
                          any(term in col.lower() for term in ['reaction', 'rt', 'response time', 'millisecond', 'msec'])]
                
                error_cols = [col for col in self.analysis_data.columns if test in col and
                             any(term in col.lower() for term in ['error', 'incorrect', 'wrong', 'miss', 'false'])]
                
                # Skip if we don't have both
                if not rt_cols or not error_cols:
                    continue
                
                # Use the first RT and error metric
                rt_col = rt_cols[0]
                error_col = error_cols[0]
                
                # Create scatter plot
                plt.figure(figsize=(10, 8))
                
                # Get the data
                plot_data = self.analysis_data[[rt_col, error_col]].dropna()
                
                if len(plot_data) < 5:
                    continue
                
                # Create scatter plot
                plt.scatter(
                    plot_data[rt_col],
                    plot_data[error_col],
                    alpha=0.7,
                    c='blue',
                    s=50
                )
                
                # Add trend line
                m, b = np.polyfit(plot_data[rt_col], plot_data[error_col], 1)
                plt.plot(plot_data[rt_col], m*plot_data[rt_col] + b, 'r-', lw=2)
                
                # Calculate correlation
                r, p = stats.pearsonr(plot_data[rt_col], plot_data[error_col])
                
                # Add correlation to title
                plt.title(f"{test}: Reaction Time vs Error Rate\nr={r:.2f}, p={p:.3f}")
                plt.xlabel(f"Reaction Time ({rt_col})")
                plt.ylabel(f"Error Rate ({error_col})")
                
                # Add quadrant labels
                x_mean = plot_data[rt_col].mean()
                y_mean = plot_data[error_col].mean()
                
                plt.axvline(x=x_mean, color='gray', linestyle='--', alpha=0.5)
                plt.axhline(y=y_mean, color='gray', linestyle='--', alpha=0.5)
                
                plt.text(plot_data[rt_col].min(), plot_data[error_col].min(), 
                         "Fast & Accurate", ha='left', va='bottom', 
                         bbox=dict(boxstyle="round,pad=0.3", fc="lightgreen", alpha=0.3))
                
                plt.text(plot_data[rt_col].max(), plot_data[error_col].min(), 
                         "Slow & Accurate", ha='right', va='bottom',
                         bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.3))
                
                plt.text(plot_data[rt_col].min(), plot_data[error_col].max(), 
                         "Fast & Inaccurate", ha='left', va='top',
                         bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.3))
                
                plt.text(plot_data[rt_col].max(), plot_data[error_col].max(), 
                         "Slow & Inaccurate", ha='right', va='top',
                         bbox=dict(boxstyle="round,pad=0.3", fc="lightcoral", alpha=0.3))
                
                plt.tight_layout()
                plt.savefig(os.path.join(self.output_dir, f"{test.replace(' ', '_')}_RT_vs_Error.png"))
                plt.close()
                
                print(f"Saved visualization: {test.replace(' ', '_')}_RT_vs_Error.png")
    
    def export_results(self, export=False):
        """Export analysis results to CSV files."""
        if not export:
            return
        
        # Create results directory if it doesn't exist
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True)
        
        # Export RT-Accuracy correlations
        if hasattr(self, 'rt_accuracy_correlations') and not self.rt_accuracy_correlations.empty:
            self.rt_accuracy_correlations.to_csv(os.path.join(self.output_dir, 'rt_accuracy_correlations.csv'), index=False)
            print(f"Exported: rt_accuracy_correlations.csv")
        
        # Export error correlations
        if hasattr(self, 'error_correlations') and not self.error_correlations.empty:
            self.error_correlations.to_csv(os.path.join(self.output_dir, 'error_correlations.csv'), index=False)
            print(f"Exported: error_correlations.csv")
        
        # Export domain correlations
        if hasattr(self, 'domain_correlations') and not self.domain_correlations.empty:
            self.domain_correlations.to_csv(os.path.join(self.output_dir, 'domain_rt_error_correlations.csv'), index=False)
            print(f"Exported: domain_rt_error_correlations.csv")
        
        # Export merged analysis data
        if hasattr(self, 'analysis_data'):
            self.analysis_data.to_csv(os.path.join(self.output_dir, 'reaction_time_error_data.csv'))
            print(f"Exported: reaction_time_error_data.csv")
    
    def run_analysis(self, visualize=False, export=False):
        """Run the complete analysis pipeline."""
        print("\n" + "="*50)
        print("Reaction Time and Error Analysis")
        print("="*50)
        
        # Load data
        if not self.load_data():
            print("Failed to load data, analysis aborted")
            return False
        
        # Prepare data
        if not any([
            self.prepare_reaction_time_data(),
            self.prepare_error_data(),
            self.prepare_accuracy_data()
        ]):
            print("Failed to prepare any data, analysis aborted")
            return False
        
        # Merge data for analysis
        if not self.merge_analysis_data():
            print("Failed to merge datasets, analysis aborted")
            return False
        
        # Run analyses
        print("\n" + "-"*50)
        print("Running Analyses")
        print("-"*50)
        
        self.analyze_rt_accuracy_relationship()
        self.analyze_error_patterns()
        self.analyze_cognitive_domain_relationships()
        
        # Visualize and export results
        if visualize:
            print("\n" + "-"*50)
            print("Generating Visualizations")
            print("-"*50)
            self.visualize_results(visualize=True)
        
        if export:
            print("\n" + "-"*50)
            print("Exporting Results")
            print("-"*50)
            self.export_results(export=True)
        
        print("\n" + "="*50)
        print("Analysis Complete")
        print("="*50)
        
        return True


def main():
    """Main function to run the analysis."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Reaction Time and Error Analysis')
    parser.add_argument('--visualize', action='store_true', help='Generate visualizations')
    parser.add_argument('--export', action='store_true', help='Export results to CSV')
    args = parser.parse_args()
    
    # Run the analysis
    analyzer = ReactionTimeAnalysis()
    analyzer.run_analysis(visualize=args.visualize, export=args.export)


if __name__ == "__main__":
    main()

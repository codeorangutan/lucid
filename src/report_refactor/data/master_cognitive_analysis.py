#!/usr/bin/env python3
"""
Master Cognitive Analysis Script

This comprehensive script runs all cognitive analyses and flags significant relationships.
It integrates multiple analysis components including:
1. ADHD symptom correlation with cognitive domains
2. Reaction time and error analysis
3. ADHD presentation differences in cognitive performance
4. DSM-5 symptom-specific cognitive profiles

Usage:
    python master_cognitive_analysis.py [--visualize] [--export] [--analysis_type ALL|ADHD|RT|DOMAIN|SYMPTOM]

Options:
    --visualize         Generate visualizations of the analyses
    --export            Export results to CSV files
    --analysis_type     Specify which analysis to run (default: ALL)
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
import json
import datetime
import logging

# Add parent directory to path for imports
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
sys.path.append(str(parent_dir))

# Try to import the adhd_cognitive_analysis script if it exists
try:
    from data.adhd_cognitive_analysis import ADHDCognitiveAnalysis
except ImportError:
    print("Warning: adhd_cognitive_analysis.py not found. ADHD-specific analyses will be limited.")
    ADHDCognitiveAnalysis = None

# Define paths
DB_PATH = os.path.join(script_dir, "cognitive_analysis.db")
if not os.path.exists(DB_PATH):
    # The database is in the current directory (data folder)
    DB_PATH = os.path.join(os.path.dirname(__file__), "cognitive_analysis.db")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(script_dir, "cognitive_analysis.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CognitiveAnalysis")

# Define ADHD DSM-5 criteria mapping
DSM5_CRITERIA = {
    'Inattentive': [1, 2, 3, 4, 5, 6, 7, 8, 9],  # Items 1-9
    'Hyperactive-Impulsive': [10, 11, 12, 13, 14, 15, 16, 17, 18]  # Items 10-18
}

# Define cognitive domains of interest
COGNITIVE_DOMAINS = [
    'Neurocognition Index (NCI)',
    'Composite Memory',
    'Reaction Time',
    'Complex Attention',
    'Cognitive Flexibility',
    'Processing Speed',
    'Executive Function',
    'Simple Attention',
    'Motor Speed'
]

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

class MasterCognitiveAnalysis:
    """
    Master class for comprehensive cognitive analysis.
    Integrates multiple analysis components and flags significant findings.
    """
    
    def __init__(self, db_path=DB_PATH):
        """Initialize the master analysis with the database path."""
        self.db_path = db_path
        self.conn = None
        self.output_dir = script_dir / 'results'
        self.output_dir.mkdir(exist_ok=True)
        
        # Data containers
        self.patients_data = None
        self.cognitive_data = None
        self.asrs_data = None
        self.subtest_data = None
        self.merged_data = None
        
        # Results containers
        self.domain_symptom_correlations = None
        self.domain_presentation_differences = None
        self.rt_accuracy_correlations = None
        self.error_correlations = None
        self.significant_findings = []
        
        # Timestamp for this analysis run
        self.analysis_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Initialized Master Cognitive Analysis with DB: {db_path}")
    
    def connect_to_db(self):
        """Connect to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            return False
    
    def load_all_data(self):
        """Load all required data from the SQLite database."""
        try:
            if not self.conn:
                if not self.connect_to_db():
                    return False
            
            # Load patient data
            logger.info("Loading patient data...")
            try:
                self.patient_data = pd.read_sql_query(
                    "SELECT * FROM patients", self.conn
                )
                logger.info(f"Loaded {len(self.patient_data)} patient records")
            except Exception as e:
                logger.error(f"Error loading patient data: {e}")
                self.patient_data = pd.DataFrame()
            
            # Load cognitive scores
            logger.info("Loading cognitive scores...")
            try:
                self.cognitive_data = pd.read_sql_query(
                    "SELECT * FROM cognitive_scores", self.conn
                )
                logger.info(f"Loaded {len(self.cognitive_data)} cognitive scores")
            except Exception as e:
                logger.error(f"Error loading cognitive scores: {e}")
                self.cognitive_data = pd.DataFrame()
            
            # Load ASRS responses
            logger.info("Loading ASRS responses...")
            try:
                self.asrs_data = pd.read_sql_query(
                    "SELECT * FROM asrs_responses", self.conn
                )
                logger.info(f"Loaded {len(self.asrs_data)} ASRS responses")
            except Exception as e:
                logger.error(f"Error loading ASRS responses: {e}")
                self.asrs_data = pd.DataFrame()
            
            # Load subtest results
            logger.info("Loading subtest results...")
            try:
                self.subtest_data = pd.read_sql_query(
                    "SELECT * FROM subtest_results", self.conn
                )
                logger.info(f"Loaded {len(self.subtest_data)} subtest results")
            except Exception as e:
                logger.error(f"Error loading subtest results: {e}")
                self.subtest_data = pd.DataFrame()
            
            # Check if we have any data
            if (self.patient_data.empty and self.cognitive_data.empty and 
                self.asrs_data.empty and self.subtest_data.empty):
                logger.error("No data loaded from database")
                return False
            
            logger.info("Successfully loaded all data")
            return True
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def process_asrs_data(self):
        """Process ASRS responses and categorize into DSM-5 criteria."""
        if self.asrs_data is None or len(self.asrs_data) == 0:
            logger.error("No ASRS data available for processing")
            # Create empty DataFrames to avoid errors in later analysis
            self.asrs_dsm_criteria = pd.DataFrame()
            self.asrs_presentations = pd.DataFrame()
            return False
        
        try:
            # Convert responses to binary clinical significance
            def is_clinically_significant(row):
                question_num = row['question_number']
                part = row['part']
                response = row['response']
                
                # Part A questions (1-6)
                if part == 'A':
                    if question_num in [1, 2, 3]:
                        return response in ['Often', 'Very Often']
                    elif question_num in [4, 5, 6]:
                        return response in ['Sometimes', 'Often', 'Very Often']
                # Part B questions (7-18)
                elif part == 'B':
                    return response in ['Often', 'Very Often']
                
                return False
            
            # Apply significance function
            self.asrs_data['is_significant'] = self.asrs_data.apply(is_clinically_significant, axis=1)
            
            # Map questions to DSM-5 criteria
            # Inattention: Questions 1-4, 7-11 (Part A: 1-4, Part B: 7-11)
            # Hyperactivity/Impulsivity: Questions 5-6, 12-18 (Part A: 5-6, Part B: 12-18)
            
            # Create mapping dictionary
            dsm_mapping = {}
            
            # Inattention criteria
            for q in [1, 2, 3, 4]:
                dsm_mapping[(q, 'A')] = 'Inattention'
            for q in [7, 8, 9, 10, 11]:
                dsm_mapping[(q, 'B')] = 'Inattention'
            
            # Hyperactivity/Impulsivity criteria
            for q in [5, 6]:
                dsm_mapping[(q, 'A')] = 'Hyperactivity/Impulsivity'
            for q in [12, 13, 14, 15, 16, 17, 18]:
                dsm_mapping[(q, 'B')] = 'Hyperactivity/Impulsivity'
            
            # Apply mapping
            self.asrs_data['dsm_criteria'] = self.asrs_data.apply(
                lambda row: dsm_mapping.get((row['question_number'], row['part']), 'Unknown'), 
                axis=1
            )
            
            # Group by patient and DSM criteria to count significant symptoms
            dsm_counts = self.asrs_data.groupby(['patient_id', 'dsm_criteria'])['is_significant'].sum().reset_index()
            
            # Pivot to get counts by criteria type
            dsm_pivot = dsm_counts.pivot(index='patient_id', columns='dsm_criteria', values='is_significant').reset_index()
            
            # Handle missing columns
            if 'Inattention' not in dsm_pivot.columns:
                dsm_pivot['Inattention'] = 0
            if 'Hyperactivity/Impulsivity' not in dsm_pivot.columns:
                dsm_pivot['Hyperactivity/Impulsivity'] = 0
            if 'Unknown' in dsm_pivot.columns:
                dsm_pivot = dsm_pivot.drop(columns=['Unknown'])
            
            # Fill NAs with 0
            dsm_pivot = dsm_pivot.fillna(0)
            
            # Store processed data
            self.asrs_dsm_criteria = dsm_pivot
            
            # Determine ADHD presentation
            def determine_presentation(row):
                # Threshold for clinical significance (≥6 symptoms)
                threshold = 6
                inattention = row.get('Inattention', 0)
                hyperactivity = row.get('Hyperactivity/Impulsivity', 0)
                
                if inattention >= threshold and hyperactivity >= threshold:
                    return 'Combined'
                elif inattention >= threshold:
                    return 'Predominantly Inattentive'
                elif hyperactivity >= threshold:
                    return 'Predominantly Hyperactive/Impulsive'
                else:
                    return 'Subclinical'
            
            # Apply presentation determination
            dsm_pivot['presentation'] = dsm_pivot.apply(determine_presentation, axis=1)
            
            # Create presentations DataFrame
            self.asrs_presentations = dsm_pivot[['patient_id', 'presentation']].copy()
            
            logger.info(f"Processed ASRS data for {len(self.asrs_presentations)} patients")
            logger.info(f"ADHD Presentations: {self.asrs_presentations['presentation'].value_counts().to_dict()}")
            
            return True
        except Exception as e:
            logger.error(f"Error processing ASRS data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Create empty DataFrames to avoid errors in later analysis
            self.asrs_dsm_criteria = pd.DataFrame()
            self.asrs_presentations = pd.DataFrame()
            return False
    
    def reshape_cognitive_data(self):
        """Reshape cognitive data for analysis."""
        if self.cognitive_data is None or len(self.cognitive_data) == 0:
            logger.error("No cognitive data available for reshaping")
            return False
        
        try:
            # Convert standard_score to numeric if it's not already
            try:
                self.cognitive_data['standard_score'] = pd.to_numeric(self.cognitive_data['standard_score'], errors='coerce')
                logger.info("Converted standard_score to numeric")
            except Exception as e:
                logger.warning(f"Error converting standard_score to numeric: {e}")
            
            # Pivot cognitive data to have domains as columns
            cognitive_pivot = self.cognitive_data.pivot_table(
                index='patient_id',
                columns='domain',
                values='standard_score',
                aggfunc='first'  # Use first value in case of duplicates
            )
            
            if cognitive_pivot.empty:
                logger.warning("Pivot table is empty after reshaping cognitive data")
                self.cognitive_pivot = pd.DataFrame()
                return False
            
            # Fill missing values with median for each domain
            for column in cognitive_pivot.columns:
                try:
                    # Check if column has any non-null values
                    non_null_values = cognitive_pivot[column].dropna()
                    if len(non_null_values) > 0:
                        median_val = non_null_values.median()
                        cognitive_pivot[column] = cognitive_pivot[column].fillna(median_val)
                    else:
                        # If column is all nulls, fill with 0 or appropriate default
                        logger.warning(f"Column {column} has no valid values, filling with 0")
                        cognitive_pivot[column] = cognitive_pivot[column].fillna(0)
                except Exception as e:
                    logger.warning(f"Error calculating median for column {column}: {e}")
                    cognitive_pivot[column] = cognitive_pivot[column].fillna(0)
            
            self.cognitive_pivot = cognitive_pivot
            logger.info(f"Reshaped cognitive data into pivot table with shape {cognitive_pivot.shape}")
            return True
        except Exception as e:
            logger.error(f"Error reshaping cognitive data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Create an empty DataFrame to avoid errors in merge_datasets
            self.cognitive_pivot = pd.DataFrame()
            return False
    
    def reshape_subtest_data(self):
        """Reshape subtest data for analysis."""
        if self.subtest_data is None:
            logger.error("No subtest data available for reshaping")
            return False
        
        # Process reaction time data
        rt_data = self.subtest_data[
            (self.subtest_data['subtest_name'].isin(REACTION_TIME_TESTS)) & 
            (self.subtest_data['metric'].str.contains('Reaction Time|RT|Response Time|Milliseconds|msec', 
                                                     case=False, na=False))
        ]
        
        # Process error data
        error_data = self.subtest_data[
            (self.subtest_data['subtest_name'].isin(ERROR_TESTS)) & 
            (self.subtest_data['metric'].str.contains('Error|Incorrect|Wrong|Miss|False', 
                                                    case=False, na=False))
        ]
        
        # Process accuracy data
        accuracy_data = self.subtest_data[
            (self.subtest_data['subtest_name'].isin(ERROR_TESTS + REACTION_TIME_TESTS)) & 
            (self.subtest_data['metric'].str.contains('Correct|Accuracy|Right|Hit', 
                                                     case=False, na=False))
        ]
        
        # Create pivot tables
        if len(rt_data) > 0:
            rt_pivot = rt_data.pivot_table(
                index='patient_id',
                columns=['subtest_name', 'metric'],
                values='score'
            )
            rt_pivot.columns = [f"{test}_{metric}" for test, metric in rt_pivot.columns]
            self.rt_pivot = rt_pivot
        
        if len(error_data) > 0:
            error_pivot = error_data.pivot_table(
                index='patient_id',
                columns=['subtest_name', 'metric'],
                values='score'
            )
            error_pivot.columns = [f"{test}_{metric}" for test, metric in error_pivot.columns]
            self.error_pivot = error_pivot
        
        if len(accuracy_data) > 0:
            accuracy_pivot = accuracy_data.pivot_table(
                index='patient_id',
                columns=['subtest_name', 'metric'],
                values='score'
            )
            accuracy_pivot.columns = [f"{test}_{metric}" for test, metric in accuracy_pivot.columns]
            self.accuracy_pivot = accuracy_pivot
        
        logger.info(f"Reshaped subtest data: RT={len(rt_data)}, Error={len(error_data)}, Accuracy={len(accuracy_data)}")
        
        return True
    
    def merge_datasets(self):
        """Merge processed datasets for comprehensive analysis."""
        try:
            datasets = []
            
            # Add cognitive data
            if hasattr(self, 'cognitive_pivot') and isinstance(self.cognitive_pivot, pd.DataFrame) and not self.cognitive_pivot.empty:
                logger.info(f"Adding cognitive_pivot to merged dataset: {self.cognitive_pivot.shape}")
                datasets.append(self.cognitive_pivot)
            else:
                logger.warning("cognitive_pivot not available for merging or is empty")
            
            # Add ADHD presentation data
            if hasattr(self, 'asrs_presentations') and isinstance(self.asrs_presentations, pd.DataFrame) and len(self.asrs_presentations) > 0:
                try:
                    # Make a copy to avoid modifying the original
                    presentations_df = self.asrs_presentations.copy()
                    # Ensure patient_id is the right type for indexing
                    presentations_df['patient_id'] = presentations_df['patient_id'].astype(int)
                    presentations_df = presentations_df.set_index('patient_id')
                    logger.info(f"Adding asrs_presentations to merged dataset: {presentations_df.shape}")
                    datasets.append(presentations_df)
                except Exception as e:
                    logger.error(f"Error preparing asrs_presentations for merge: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.warning("asrs_presentations not available for merging or is empty")
            
            # Add reaction time data
            if hasattr(self, 'rt_pivot') and isinstance(self.rt_pivot, pd.DataFrame) and not self.rt_pivot.empty:
                logger.info(f"Adding rt_pivot to merged dataset: {self.rt_pivot.shape}")
                datasets.append(self.rt_pivot)
            else:
                logger.warning("rt_pivot not available for merging or is empty")
            
            # Add error data
            if hasattr(self, 'error_pivot') and isinstance(self.error_pivot, pd.DataFrame) and not self.error_pivot.empty:
                logger.info(f"Adding error_pivot to merged dataset: {self.error_pivot.shape}")
                datasets.append(self.error_pivot)
            else:
                logger.warning("error_pivot not available for merging or is empty")
            
            # Add accuracy data
            if hasattr(self, 'accuracy_pivot') and isinstance(self.accuracy_pivot, pd.DataFrame) and not self.accuracy_pivot.empty:
                logger.info(f"Adding accuracy_pivot to merged dataset: {self.accuracy_pivot.shape}")
                datasets.append(self.accuracy_pivot)
            else:
                logger.warning("accuracy_pivot not available for merging or is empty")
            
            # Check if we have any datasets to merge
            if len(datasets) == 0:
                logger.error("No datasets available for merging")
                # Create an empty DataFrame to avoid errors in later analysis
                self.merged_data = pd.DataFrame()
                return False
            
            # Merge all datasets on patient_id
            logger.info(f"Merging {len(datasets)} datasets")
            
            if len(datasets) == 1:
                # If only one dataset, no need to merge
                self.merged_data = datasets[0].copy()
            else:
                try:
                    # Use functools.reduce to merge multiple dataframes
                    from functools import reduce
                    # Use outer join to keep all patients
                    self.merged_data = reduce(lambda left, right: pd.merge(
                        left, right, left_index=True, right_index=True, how='outer'), datasets)
                except Exception as e:
                    logger.error(f"Error during merge operation: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # If merge fails, use the first dataset as a fallback
                    logger.warning("Using first dataset as fallback due to merge failure")
                    self.merged_data = datasets[0].copy()
            
            # Handle NaNs in the merged dataset
            try:
                na_count_before = self.merged_data.isna().sum().sum()
                if na_count_before > 0:
                    logger.warning(f"Merged dataset contains {na_count_before} NaN values, filling with appropriate defaults")
                    # Fill NaN values with median for each column, or 0 if all NaN
                    for col in self.merged_data.columns:
                        try:
                            non_null_values = self.merged_data[col].dropna()
                            if len(non_null_values) > 0:
                                # If we have some valid values, use median for numeric columns
                                if pd.api.types.is_numeric_dtype(self.merged_data[col]):
                                    median_val = non_null_values.median()
                                    self.merged_data[col] = self.merged_data[col].fillna(median_val)
                                else:
                                    # For non-numeric columns, use mode or a default value
                                    mode_val = non_null_values.mode()[0] if not non_null_values.mode().empty else "Unknown"
                                    self.merged_data[col] = self.merged_data[col].fillna(mode_val)
                            else:
                                # If column is all nulls, fill with 0 for numeric or "Unknown" for non-numeric
                                if pd.api.types.is_numeric_dtype(self.merged_data[col]):
                                    default_val = 0
                                else:
                                    default_val = "Unknown"
                                logger.warning(f"Column {col} has no valid values, filling with {default_val}")
                                self.merged_data[col] = self.merged_data[col].fillna(default_val)
                        except Exception as e:
                            logger.warning(f"Error handling NaNs for column {col}: {e}")
                            # Fallback to filling with 0 or "Unknown"
                            if pd.api.types.is_numeric_dtype(self.merged_data[col]):
                                self.merged_data[col] = self.merged_data[col].fillna(0)
                            else:
                                self.merged_data[col] = self.merged_data[col].fillna("Unknown")
            except Exception as e:
                logger.error(f"Error handling NaNs in merged dataset: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            logger.info(f"Successfully merged datasets: {self.merged_data.shape}")
            return True
            
        except Exception as e:
            logger.error(f"Error merging datasets: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Create an empty DataFrame to avoid errors in later analysis
            self.merged_data = pd.DataFrame()
            return False
    
    def run_analysis(self, visualize=False, export=False, analysis_type='ALL'):
        """Run the complete analysis pipeline."""
        logger.info("\n" + "="*50)
        logger.info("Starting Master Cognitive Analysis")
        logger.info("="*50)
        
        # Load data
        if not self.load_all_data():
            logger.error("Failed to load data, analysis aborted")
            return False
        
        # Process data
        logger.info("\n" + "-"*50)
        logger.info("Processing Data")
        logger.info("-"*50)
        
        # Track which components were successfully processed
        successful_components = {
            'asrs': False,
            'cognitive': False,
            'subtest': False,
            'merged': False
        }
        
        try:
            logger.info("Processing ASRS data...")
            if self.process_asrs_data():
                successful_components['asrs'] = True
        except Exception as e:
            logger.error(f"Error processing ASRS data: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        try:
            logger.info("Reshaping cognitive data...")
            if self.reshape_cognitive_data():
                successful_components['cognitive'] = True
        except Exception as e:
            logger.error(f"Error reshaping cognitive data: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        try:
            logger.info("Reshaping subtest data...")
            if self.reshape_subtest_data():
                successful_components['subtest'] = True
        except Exception as e:
            logger.error(f"Error reshaping subtest data: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Merge datasets
        logger.info("Merging datasets...")
        try:
            if self.merge_datasets():
                successful_components['merged'] = True
            else:
                logger.warning("Dataset merging was incomplete, some analyses may be limited")
        except Exception as e:
            logger.error(f"Error during dataset merge: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Run analyses based on analysis_type and available data
        logger.info("\n" + "-"*50)
        logger.info(f"Running Analyses (Type: {analysis_type})")
        logger.info("-"*50)
        
        # Only run analyses if we have merged data
        if not successful_components['merged'] or not hasattr(self, 'merged_data') or not isinstance(self.merged_data, pd.DataFrame) or self.merged_data.empty:
            logger.error("No merged data available, skipping analyses")
            return False
        
        # Run analyses based on available data
        if analysis_type in ['ALL', 'ADHD'] and successful_components['cognitive'] and successful_components['asrs']:
            try:
                self.analyze_domain_symptom_correlations()
            except Exception as e:
                logger.error(f"Error in domain-symptom correlation analysis: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            try:
                self.analyze_domain_presentation_differences()
            except Exception as e:
                logger.error(f"Error in domain-presentation difference analysis: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning("Skipping ADHD analyses due to missing data components")
        
        if analysis_type in ['ALL', 'RT'] and successful_components['subtest']:
            try:
                self.analyze_rt_accuracy_relationships()
            except Exception as e:
                logger.error(f"Error in RT-accuracy relationship analysis: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            try:
                self.analyze_error_patterns()
            except Exception as e:
                logger.error(f"Error in error pattern analysis: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning("Skipping RT analyses due to missing data components")
        
        if analysis_type in ['ALL', 'SYMPTOM'] and successful_components['cognitive'] and successful_components['asrs']:
            try:
                self.analyze_domain_specific_symptoms()
            except Exception as e:
                logger.error(f"Error in domain-specific symptom analysis: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning("Skipping symptom analyses due to missing data components")
        
        # Visualize and export results if requested
        if visualize:
            try:
                self.visualize_results(visualize=True)
            except Exception as e:
                logger.error(f"Error generating visualizations: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        if export:
            try:
                self.export_results(export=True)
            except Exception as e:
                logger.error(f"Error exporting results: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # Remove the call to export_html_report as it's not implemented
            # try:
            #     self.export_html_report(self.analysis_timestamp)
            # except Exception as e:
            #     logger.error(f"Error exporting HTML report: {e}")
            #     import traceback
            #     logger.error(traceback.format_exc())
        
        logger.info("\n" + "="*50)
        logger.info("Master Cognitive Analysis Complete")
        logger.info("="*50)
        
        return True


def main():
    """Main function to run the analysis."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Master Cognitive Analysis')
    parser.add_argument('--visualize', action='store_true', help='Generate visualizations')
    parser.add_argument('--export', action='store_true', help='Export results to CSV files')
    parser.add_argument('--analysis_type', choices=['ALL', 'ADHD', 'RT', 'DOMAIN', 'SYMPTOM'], 
                        default='ALL', help='Specify which analysis to run')
    args = parser.parse_args()
    
    # Run the analysis
    analyzer = MasterCognitiveAnalysis()
    analyzer.run_analysis(
        visualize=args.visualize,
        export=args.export,
        analysis_type=args.analysis_type
    )


if __name__ == "__main__":
    main()

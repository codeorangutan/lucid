#!/usr/bin/env python3
"""
Speed vs Accuracy Analysis Script

This script analyzes the relationship between speed and accuracy metrics
for various cognitive tests from the cognitive_analysis database.

Tests analyzed:
1. SDC (Symbol Digit Coding): Correct Responses vs Errors
2. Stroop Test: Reaction Time Correct vs Commission Errors
3. SAT (Shifting Attention Test): Correct Reaction Time vs Errors
4. CPT (Continuous Performance Test): Choice Reaction Time vs Summed Errors
5. Reasoning: Average Correct Reaction Time vs Summed Errors

The script generates:
1. Correlation statistics for each test
2. Scatter plots with regression lines
3. Cached data for future use
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import json
import logging
from io import BytesIO

# Set up logging
logging.basicConfig(
    filename='speed_accuracy_analysis.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # Overwrite existing log file
)

# Define test pairs for analysis
# Format: (test_name, speed_metric, error_metric, speed_label, error_label, chart_title)
TEST_PAIRS = [
    (
        "Symbol Digit Coding", 
        "Correct Responses", 
        "Errors", 
        "Correct Responses\n(Higher=Better)",
        "Errors\n(Higher=Worse)",
        "SDC: Speed vs Accuracy"
    ),
    (
        "Stroop Test", 
        "Reaction Time Correct", 
        "Commission Errors", 
        "Reaction Time\n(Lower=Faster)",
        "Commission Errors\n(Higher=Worse)",
        "Stroop: Speed vs Accuracy"
    ),
    (
        "Shifting Attention Test", 
        "Correct Reaction Time", 
        "Errors", 
        "Reaction Time\n(Lower=Faster)",
        "Errors\n(Higher=Worse)",
        "SAT: Speed vs Accuracy"
    ),
    (
        "Continuous Performance Test", 
        "Reaction Time", 
        ["Omission Errors", "Commission Errors"], 
        "Reaction Time\n(Lower=Faster)",
        "Total Errors\n(Higher=Worse)",
        "CPT: Speed vs Accuracy"
    ),
    (
        "Reasoning", 
        "Average Correct Reaction Time", 
        ["Commission Errors", "Omission Errors"], 
        "Reaction Time\n(Lower=Faster)",
        "Total Errors\n(Higher=Worse)",
        "Reasoning: Speed vs Accuracy"
    )
]

def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    cache_dir = os.path.join('data', 'analysis_output', 'cached_data')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_population_data(db_path, test_name, speed_metric, error_metric):
    """
    Query the database for population data for a specific test.
    
    Args:
        db_path: Path to the SQLite database
        test_name: Name of the test (e.g., "Shifting Attention Test")
        speed_metric: Name of the speed metric
        error_metric: Name of the error metric or list of metrics to sum
        
    Returns:
        DataFrame with patient_id, speed_score, and error_score columns
    """
    logging.info(f"Querying database for {test_name}: {speed_metric} vs {error_metric}")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Handle single error metric
        if isinstance(error_metric, str):
            query = """
            SELECT sr1.patient_id, 
                   sr1.score as speed_score, 
                   sr2.score as error_score
            FROM subtest_results sr1
            JOIN subtest_results sr2 ON sr1.patient_id = sr2.patient_id
            WHERE sr1.subtest_name LIKE ?
            AND sr1.metric LIKE ? 
            AND sr2.subtest_name LIKE ?
            AND sr2.metric LIKE ?
            """
            population_df = pd.read_sql_query(
                query, conn, 
                params=(f"%{test_name}%", f"%{speed_metric}%", f"%{test_name}%", f"%{error_metric}%")
            )
        
        # Handle multiple error metrics that need to be summed
        else:
            # First get the speed data
            speed_query = """
            SELECT patient_id, 
                   score as speed_score
            FROM subtest_results
            WHERE subtest_name LIKE ?
            AND metric LIKE ?
            """
            speed_df = pd.read_sql_query(
                speed_query, conn, 
                params=(f"%{test_name}%", f"%{speed_metric}%")
            )
            
            # Then get each error metric and sum them
            error_df = None
            for err_metric in error_metric:
                query = """
                SELECT patient_id, 
                       score as error_score
                FROM subtest_results
                WHERE subtest_name LIKE ?
                AND metric LIKE ?
                """
                temp_df = pd.read_sql_query(
                    query, conn, 
                    params=(f"%{test_name}%", f"%{err_metric}%")
                )
                
                if error_df is None:
                    error_df = temp_df
                else:
                    # Join with existing error data and sum the scores
                    error_df = pd.merge(error_df, temp_df, on='patient_id', suffixes=('', '_new'))
                    error_df['error_score'] = error_df['error_score'] + error_df['error_score_new']
                    error_df = error_df.drop('error_score_new', axis=1)
            
            # Join speed and error data
            if error_df is not None and not speed_df.empty and not error_df.empty:
                population_df = pd.merge(speed_df, error_df, on='patient_id')
            else:
                population_df = pd.DataFrame()
        
        conn.close()
        
        logging.info(f"Found {len(population_df)} patients with {test_name} data")
        return population_df
    
    except Exception as e:
        logging.error(f"Error querying database for {test_name}: {e}")
        return pd.DataFrame()

def clean_data(df):
    """
    Clean the data by converting to numeric and removing NaN values.
    
    Args:
        df: DataFrame with speed_score and error_score columns
        
    Returns:
        Cleaned DataFrame
    """
    try:
        # Convert to numeric and drop NaNs
        df['speed_score'] = pd.to_numeric(df['speed_score'], errors='coerce')
        df['error_score'] = pd.to_numeric(df['error_score'], errors='coerce')
        df = df.dropna(subset=['speed_score', 'error_score'])
        
        # Remove extreme outliers (beyond 3 standard deviations)
        for col in ['speed_score', 'error_score']:
            mean = df[col].mean()
            std = df[col].std()
            df = df[(df[col] > mean - 3*std) & (df[col] < mean + 3*std)]
        
        return df
    
    except Exception as e:
        logging.error(f"Error cleaning data: {e}")
        return df

def calculate_regression(df):
    """
    Calculate regression parameters for the dataset.
    
    Args:
        df: DataFrame with speed_score and error_score columns
        
    Returns:
        Dictionary of regression parameters
    """
    try:
        # Calculate linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            df['speed_score'], df['error_score'])
        
        # Calculate Spearman correlation
        corr, p = stats.spearmanr(df['speed_score'], df['error_score'])
        
        return {
            'slope': float(slope),
            'intercept': float(intercept),
            'r_value': float(r_value),
            'p_value': float(p_value),
            'std_err': float(std_err),
            'corr': float(corr),
            'p': float(p),
            'n': len(df)
        }
    
    except Exception as e:
        logging.error(f"Error calculating regression: {e}")
        return None

def create_chart(df, regression_params, speed_label, error_label, chart_title):
    """
    Create a chart showing the relationship between speed and error metrics.
    
    Args:
        df: DataFrame with speed_score and error_score columns
        regression_params: Dictionary of regression parameters
        speed_label: Label for the speed metric
        error_label: Label for the error metric
        chart_title: Title for the chart
        
    Returns:
        BytesIO object containing the chart image
    """
    try:
        plt.figure(figsize=(10, 8))
        
        # Extract regression parameters
        slope = regression_params['slope']
        intercept = regression_params['intercept']
        corr = regression_params['corr']
        p = regression_params['p']
        n = regression_params['n']
        
        # Generate x values across the range for the line
        x_min, x_max = df['speed_score'].min(), df['speed_score'].max()
        x_line = np.linspace(x_min, x_max, 100)
        y_line = slope * x_line + intercept
        
        # Plot population data points with transparency
        plt.scatter(df['speed_score'], df['error_score'], color='gray', alpha=0.3, s=30)
        
        # Plot regression line
        plt.plot(x_line, y_line, color='red', linewidth=2)
        
        # Clean labels and add interpretation notes
        plt.title(f"{chart_title}\nPopulation Spearman R={corr:.2f}, p={p:.6f}, N={n}")
        plt.xlabel(speed_label)
        plt.ylabel(error_label)
        plt.grid(True, alpha=0.3)
        
        # Add quadrant labels to help interpretation
        if "Higher=Better" in speed_label:
            # For tests where higher speed score is better (like SDC correct responses)
            plt.annotate("Slow & Inaccurate", xy=(x_min, df['error_score'].max()), 
                        xytext=(10, -10), textcoords='offset points', color='red')
            plt.annotate("Fast & Accurate", xy=(x_max, df['error_score'].min()), 
                        xytext=(-10, 10), textcoords='offset points', color='green')
        else:
            # For tests where lower speed score is better (reaction times)
            plt.annotate("Fast & Accurate", xy=(x_min, df['error_score'].min()), 
                        xytext=(10, 10), textcoords='offset points', color='green')
            plt.annotate("Slow & Inaccurate", xy=(x_max, df['error_score'].max()), 
                        xytext=(-10, -10), textcoords='offset points', color='red')
        
        # Save to BytesIO
        img_data = BytesIO()
        plt.savefig(img_data, format='png', dpi=150, bbox_inches='tight')
        img_data.seek(0)
        plt.close()
        
        return img_data
    
    except Exception as e:
        logging.error(f"Error creating chart: {e}")
        return None

def analyze_test(db_path, test_name, speed_metric, error_metric, speed_label, error_label, chart_title):
    """
    Analyze the relationship between speed and error metrics for a specific test.
    
    Args:
        db_path: Path to the SQLite database
        test_name: Name of the test
        speed_metric: Name of the speed metric
        error_metric: Name of the error metric or list of metrics to sum
        speed_label: Label for the speed metric
        error_label: Label for the error metric
        chart_title: Title for the chart
        
    Returns:
        Tuple of (regression_params, chart_image)
    """
    cache_dir = ensure_cache_dir()
    
    # Create cache filenames
    test_id = test_name.lower().replace(' ', '_')
    population_cache_file = os.path.join(cache_dir, f'{test_id}_population_data.csv')
    regression_cache_file = os.path.join(cache_dir, f'{test_id}_regression.json')
    
    # Try to load population data from cache
    population_df = None
    if os.path.exists(population_cache_file):
        logging.info(f"Loading cached population data from {population_cache_file}")
        try:
            population_df = pd.read_csv(population_cache_file)
        except Exception as e:
            logging.error(f"Error loading cached population data: {e}")
            population_df = None
    
    # If not in cache, query from database
    if population_df is None:
        logging.info(f"Population data not cached, querying database...")
        population_df = get_population_data(db_path, test_name, speed_metric, error_metric)
        
        # Save population data to cache
        if not population_df.empty:
            logging.info(f"Saving population data to cache: {population_cache_file}")
            try:
                population_df.to_csv(population_cache_file, index=False)
            except Exception as e:
                logging.error(f"Error saving population data to cache: {e}")
    
    if population_df is None or population_df.empty:
        logging.warning(f"No data found for {test_name}")
        return None, None
    
    # Clean the data
    clean_df = clean_data(population_df)
    if len(clean_df) < 10:
        logging.warning(f"Insufficient data points after cleaning: {len(clean_df)}")
        return None, None
    
    # Try to load regression parameters from cache
    regression_params = None
    if os.path.exists(regression_cache_file):
        logging.info(f"Loading cached regression parameters from {regression_cache_file}")
        try:
            with open(regression_cache_file, 'r') as f:
                regression_params = json.load(f)
        except Exception as e:
            logging.error(f"Error loading regression parameters: {e}")
            regression_params = None
    
    # Calculate regression if not in cache
    if regression_params is None:
        logging.info(f"Calculating regression parameters for {test_name}...")
        regression_params = calculate_regression(clean_df)
        
        # Save regression parameters to cache
        if regression_params:
            logging.info(f"Saving regression parameters to cache: {regression_cache_file}")
            try:
                with open(regression_cache_file, 'w') as f:
                    json.dump(regression_params, f)
            except Exception as e:
                logging.error(f"Error saving regression parameters: {e}")
    
    # Create chart
    if regression_params:
        logging.info(f"Creating chart for {test_name}...")
        chart_image = create_chart(clean_df, regression_params, speed_label, error_label, chart_title)
        return regression_params, chart_image
    
    return None, None

def save_chart(chart_image, test_name):
    """Save chart image to file."""
    if chart_image:
        output_dir = os.path.join('data', 'analysis_output', 'charts')
        os.makedirs(output_dir, exist_ok=True)
        
        test_id = test_name.lower().replace(' ', '_')
        output_path = os.path.join(output_dir, f'{test_id}_speed_accuracy.png')
        
        with open(output_path, 'wb') as f:
            f.write(chart_image.getvalue())
        
        logging.info(f"Saved chart to {output_path}")
        print(f"Saved chart to {output_path}")

def print_regression_summary(test_name, regression_params):
    """Print a summary of the regression results."""
    if regression_params:
        print(f"\n=== {test_name} Speed-Accuracy Analysis ===")
        print(f"Sample size: {regression_params['n']}")
        print(f"Spearman correlation: {regression_params['corr']:.3f} (p={regression_params['p']:.6f})")
        print(f"Linear regression: y = {regression_params['slope']:.3f}x + {regression_params['intercept']:.3f}")
        print(f"R-squared: {regression_params['r_value']**2:.3f}")
        
        # Interpret the correlation
        corr = regression_params['corr']
        p = regression_params['p']
        
        if p < 0.05:
            if abs(corr) < 0.3:
                strength = "weak"
            elif abs(corr) < 0.5:
                strength = "moderate"
            else:
                strength = "strong"
            
            direction = "positive" if corr > 0 else "negative"
            print(f"Interpretation: There is a statistically significant {strength} {direction} correlation")
            
            if "Symbol Digit Coding" in test_name:
                if corr < 0:
                    print("This suggests that as correct responses increase, errors tend to decrease")
                else:
                    print("This suggests that as correct responses increase, errors also tend to increase")
            else:
                if corr > 0:
                    print("This suggests that as reaction time increases (slower), errors tend to increase")
                else:
                    print("This suggests that as reaction time increases (slower), errors tend to decrease")
        else:
            print("Interpretation: No statistically significant correlation was found")

def main():
    """Main function to run the analysis for all tests."""
    db_path = 'cognitive_analysis.db'
    
    print("Starting Speed-Accuracy Analysis...")
    logging.info("Starting Speed-Accuracy Analysis")
    
    results = {}
    
    for test_info in TEST_PAIRS:
        test_name, speed_metric, error_metric, speed_label, error_label, chart_title = test_info
        
        print(f"\nAnalyzing {test_name}: {speed_metric} vs {error_metric}...")
        regression_params, chart_image = analyze_test(
            db_path, test_name, speed_metric, error_metric, 
            speed_label, error_label, chart_title
        )
        
        if regression_params and chart_image:
            results[test_name] = regression_params
            save_chart(chart_image, test_name)
            print_regression_summary(test_name, regression_params)
        else:
            print(f"Analysis failed for {test_name}")
    
    print("\nAnalysis complete. Results saved to data/analysis_output/")
    logging.info("Analysis complete")
    
    return results

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cognitive Domain Correlation Analysis

This script analyzes the pairwise correlations between cognitive domains
from the cognitive_analysis.db database.
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Set up logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='domain_correlation_analysis.log'
)
logger = logging.getLogger('domain_correlation')

def get_cognitive_domain_data(db_path='cognitive_analysis.db'):
    """
    Extract cognitive domain data from the database and pivot it for correlation analysis.
    
    Returns:
        DataFrame with patient_id as index and domains as columns
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        logger.info(f"Connected to database: {db_path}")
        
        # Query to get all cognitive domain scores
        query = """
        SELECT patient_id, domain, percentile, validity_index
        FROM cognitive_scores
        ORDER BY patient_id, domain
        """
        
        # Load data into a DataFrame
        df = pd.read_sql_query(query, conn)
        logger.info(f"Retrieved {len(df)} cognitive score records")
        
        # Close the connection
        conn.close()
        
        # Filter out invalid scores
        valid_scores = df[df['validity_index'].str.lower().isin(['1', 'yes', 'valid', 'true'])]
        logger.info(f"Filtered to {len(valid_scores)} valid cognitive score records")
        
        # Pivot the data to have domains as columns and patients as rows
        pivot_df = valid_scores.pivot(index='patient_id', columns='domain', values='percentile')
        logger.info(f"Created pivot table with {pivot_df.shape[0]} patients and {pivot_df.shape[1]} domains")
        
        return pivot_df
        
    except Exception as e:
        logger.error(f"Error retrieving cognitive domain data: {e}")
        return None

def analyze_correlations(domain_data):
    """
    Calculate and visualize pairwise correlations between cognitive domains.
    
    Args:
        domain_data: DataFrame with patient_id as index and domains as columns
    
    Returns:
        correlation_matrix: DataFrame containing the correlation coefficients
    """
    try:
        if domain_data is None or domain_data.empty:
            logger.error("No valid domain data provided for correlation analysis")
            return None
            
        # Drop the Neurocognitive Index if present (it's a composite score)
        if 'Neurocognitive Index' in domain_data.columns:
            domain_data = domain_data.drop(columns=['Neurocognitive Index'])
            logger.info("Dropped Neurocognitive Index from correlation analysis")
        
        # Calculate correlation matrix
        correlation_matrix = domain_data.corr(method='pearson')
        logger.info(f"Calculated correlation matrix of shape {correlation_matrix.shape}")
        
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Save correlation matrix to CSV
        csv_path = os.path.join(output_dir, 'cognitive_domain_correlations.csv')
        correlation_matrix.to_csv(csv_path)
        logger.info(f"Saved correlation matrix to {csv_path}")
        
        # Create heatmap visualization
        plt.figure(figsize=(12, 10))
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
        
        # Generate a custom diverging colormap
        cmap = sns.diverging_palette(230, 20, as_cmap=True)
        
        # Draw the heatmap with the mask and correct aspect ratio
        heatmap = sns.heatmap(
            correlation_matrix, 
            mask=mask,
            cmap=cmap, 
            vmax=1.0, 
            vmin=-1.0,
            center=0,
            square=True, 
            linewidths=.5, 
            cbar_kws={"shrink": .5},
            annot=True,
            fmt=".2f"
        )
        
        plt.title('Pairwise Correlations Between Cognitive Domains', fontsize=16)
        plt.tight_layout()
        
        # Save the heatmap
        heatmap_path = os.path.join(output_dir, 'cognitive_domain_correlations.png')
        plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved correlation heatmap to {heatmap_path}")
        
        # Generate a text summary of strongest correlations
        summary_path = os.path.join(output_dir, 'correlation_summary.txt')
        with open(summary_path, 'w') as f:
            f.write("Cognitive Domain Correlation Analysis\n")
            f.write("====================================\n\n")
            
            f.write("Strongest Positive Correlations:\n")
            # Get the upper triangle of the correlation matrix (excluding diagonal)
            upper_tri = correlation_matrix.where(np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool))
            # Stack the data and sort
            strongest_pos = upper_tri.stack().sort_values(ascending=False).head(5)
            for (domain1, domain2), corr in strongest_pos.items():
                f.write(f"  {domain1} and {domain2}: {corr:.3f}\n")
            
            f.write("\nStrongest Negative Correlations:\n")
            strongest_neg = upper_tri.stack().sort_values().head(5)
            for (domain1, domain2), corr in strongest_neg.items():
                f.write(f"  {domain1} and {domain2}: {corr:.3f}\n")
                
        logger.info(f"Saved correlation summary to {summary_path}")
        
        return correlation_matrix
        
    except Exception as e:
        logger.error(f"Error analyzing correlations: {e}")
        return None

def main():
    """Main function to run the correlation analysis"""
    try:
        logger.info("Starting cognitive domain correlation analysis")
        
        # Get the database path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        db_path = os.path.join(parent_dir, 'cognitive_analysis.db')
        
        # Get domain data
        domain_data = get_cognitive_domain_data(db_path)
        
        if domain_data is not None and not domain_data.empty:
            # Print basic statistics
            print(f"Analyzing data from {domain_data.shape[0]} patients across {domain_data.shape[1]} cognitive domains")
            
            # Calculate and visualize correlations
            correlation_matrix = analyze_correlations(domain_data)
            
            if correlation_matrix is not None:
                print("\nCorrelation Analysis Complete!")
                print(f"Results saved to {os.path.join(script_dir, 'output')} directory")
                
                # Print the correlation matrix to console
                print("\nCorrelation Matrix:")
                print(correlation_matrix.round(2))
                
                # Print the strongest correlations
                print("\nStrongest Positive Correlations:")
                upper_tri = correlation_matrix.where(np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool))
                strongest_pos = upper_tri.stack().sort_values(ascending=False).head(5)
                for (domain1, domain2), corr in strongest_pos.items():
                    print(f"  {domain1} and {domain2}: {corr:.3f}")
                
                print("\nStrongest Negative Correlations:")
                strongest_neg = upper_tri.stack().sort_values().head(5)
                for (domain1, domain2), corr in strongest_neg.items():
                    print(f"  {domain1} and {domain2}: {corr:.3f}")
            else:
                print("Failed to generate correlation matrix. Check the log file for details.")
        else:
            print("No valid cognitive domain data found. Check the log file for details.")
            
        logger.info("Cognitive domain correlation analysis complete")
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

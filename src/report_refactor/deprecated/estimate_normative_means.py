#!/usr/bin/env python3
"""
Estimates the raw score corresponding to a standardized score of 100 
(assumed population mean) for specified cognitive test metrics,
using interpolation if an exact match for SS=100 is not found.
"""

import sqlite3
import pandas as pd
import numpy as np
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

DB_PATH = 'cognitive_analysis.db'
TARGET_STANDARD_SCORE = 100

# Define the metrics used in the Speed Accuracy plots
# (Based on TEST_CONFIG_SPEED_ACCURACY in report_generator.py)
METRICS_TO_ANALYZE = [
    {"test": "Shifting Attention Test", "metric": "Correct Reaction Time"},
    {"test": "Shifting Attention Test", "metric": "Errors"},
    {"test": "Stroop Test", "metric": "Reaction Time Correct"},
    {"test": "Stroop Test", "metric": "Commission Errors"},
    {"test": "Reasoning", "metric": "Average Correct Reaction Time"},
    # For Reasoning, errors are summed. Analyze components:
    {"test": "Reasoning", "metric": "Commission Errors"}, 
    {"test": "Reasoning", "metric": "Omission Errors"},
    # Add metrics from other speed-accuracy pairs for completeness if desired
    # {"test": "Symbol Digit Coding", "metric": "Correct Responses"},
    # {"test": "Symbol Digit Coding", "metric": "Errors"},
    # {"test": "Continuous Performance Test", "metric": "Reaction Time"},
    # {"test": "Continuous Performance Test", "metric": "Omission Errors"},
    # {"test": "Continuous Performance Test", "metric": "Commission Errors"},
]

def get_raw_stats_for_ss(db_path, test_name, metric_name, standard_score):
    """Queries DB for raw scores for a specific standard score and calculates mean/median."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT score 
            FROM subtest_results 
            WHERE subtest_name LIKE ? 
              AND metric LIKE ? 
              AND standard_score = ?
        """
        params = (f'%{test_name}%', f'%{metric_name}%', standard_score)
        df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return None, None, 0

        scores = pd.to_numeric(df['score'], errors='coerce').dropna()
        if scores.empty:
            return None, None, 0
            
        return scores.mean(), scores.median(), len(scores)

    except sqlite3.Error as e:
        logging.error(f"DB error querying SS={standard_score} for '{test_name} - {metric_name}': {e}")
        return None, None, 0
    except Exception as e:
        logging.error(f"Error processing SS={standard_score} for '{test_name} - {metric_name}': {e}")
        return None, None, 0
    finally:
        if conn:
            conn.close()

def find_flanking_ss(db_path, test_name, metric_name, target_ss):
    """Finds nearest standard scores with data above and below the target."""
    conn = None
    ss_below, ss_above = None, None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find highest SS < target_ss with data
        query_below = """
            SELECT MAX(standard_score) 
            FROM subtest_results 
            WHERE subtest_name LIKE ? 
              AND metric LIKE ? 
              AND standard_score < ?
        """
        cursor.execute(query_below, (f'%{test_name}%', f'%{metric_name}%', target_ss))
        result_below = cursor.fetchone()
        if result_below and result_below[0] is not None:
            ss_below = result_below[0]

        # Find lowest SS > target_ss with data
        query_above = """
            SELECT MIN(standard_score) 
            FROM subtest_results 
            WHERE subtest_name LIKE ? 
              AND metric LIKE ? 
              AND standard_score > ?
        """
        cursor.execute(query_above, (f'%{test_name}%', f'%{metric_name}%', target_ss))
        result_above = cursor.fetchone()
        if result_above and result_above[0] is not None:
            ss_above = result_above[0]
            
        return ss_below, ss_above

    except sqlite3.Error as e:
        logging.error(f"DB error finding flanking SS for '{test_name} - {metric_name}': {e}")
        return None, None
    except Exception as e:
        logging.error(f"Error finding flanking SS for '{test_name} - {metric_name}': {e}")
        return None, None
    finally:
        if conn:
            conn.close()

def linear_interpolate(x, x1, y1, x2, y2):
    """Performs linear interpolation for y at point x."""
    if x1 is None or y1 is None or x2 is None or y2 is None or x1 == x2:
        return None # Cannot interpolate
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)

if __name__ == "__main__":
    print(f"--- Estimating Raw Scores Corresponding to Standard Score = {TARGET_STANDARD_SCORE} (using interpolation if needed) ---")
    results_summary = {}
    
    for item in METRICS_TO_ANALYZE:
        test = item['test']
        metric = item['metric']
        print(f"\nProcessing: {test} - {metric}")
        
        mean_r, median_r, n = get_raw_stats_for_ss(DB_PATH, test, metric, TARGET_STANDARD_SCORE)
        
        if n > 0:
            logging.info(f"Found N={n} for SS={TARGET_STANDARD_SCORE}. Est Mean Raw={mean_r:.2f}, Est Median Raw={median_r:.2f}")
            results_summary[f"{test} :: {metric}"] = {'mean': mean_r, 'median': median_r, 'n': n, 'type': 'Direct'}
        else:
            logging.warning(f"No direct data found for SS={TARGET_STANDARD_SCORE}. Attempting interpolation.")
            ss_below, ss_above = find_flanking_ss(DB_PATH, test, metric, TARGET_STANDARD_SCORE)
            
            if ss_below is None and ss_above is None:
                logging.error(f"No flanking data found for interpolation.")
                results_summary[f"{test} :: {metric}"] = {'mean': None, 'median': None, 'n': 0, 'type': 'Failed'}
                continue
                
            # Get stats for flanking points
            mean_below, median_below, n_below = (None, None, 0) if ss_below is None else get_raw_stats_for_ss(DB_PATH, test, metric, ss_below)
            mean_above, median_above, n_above = (None, None, 0) if ss_above is None else get_raw_stats_for_ss(DB_PATH, test, metric, ss_above)

            if n_below > 0 and n_above > 0:
                # Interpolate
                interpolated_mean = linear_interpolate(TARGET_STANDARD_SCORE, ss_below, mean_below, ss_above, mean_above)
                interpolated_median = linear_interpolate(TARGET_STANDARD_SCORE, ss_below, median_below, ss_above, median_above)
                logging.info(f"Interpolated from SS={ss_below} (N={n_below}) and SS={ss_above} (N={n_above}).")
                logging.info(f"  Est Mean Raw={interpolated_mean:.2f}, Est Median Raw={interpolated_median:.2f}")
                results_summary[f"{test} :: {metric}"] = {'mean': interpolated_mean, 'median': interpolated_median, 'n': 0, 'type': 'Interpolated'}
            elif n_below > 0:
                 logging.warning(f"Only found data below SS={TARGET_STANDARD_SCORE} (at SS={ss_below}, N={n_below}). Cannot interpolate.")
                 results_summary[f"{test} :: {metric}"] = {'mean': None, 'median': None, 'n': 0, 'type': 'Failed (Below Only)'}
            elif n_above > 0:
                 logging.warning(f"Only found data above SS={TARGET_STANDARD_SCORE} (at SS={ss_above}, N={n_above}). Cannot interpolate.")
                 results_summary[f"{test} :: {metric}"] = {'mean': None, 'median': None, 'n': 0, 'type': 'Failed (Above Only)'}
            else:
                logging.error(f"Found flanking SS ({ss_below}, {ss_above}) but no valid raw scores associated with them.")
                results_summary[f"{test} :: {metric}"] = {'mean': None, 'median': None, 'n': 0, 'type': 'Failed'}

    print("\n--- Summary of Estimated Raw Scores (for SS=100) ---")
    for key, value in results_summary.items():
        if value['type'] == 'Direct':
            print(f"- {key}: [Direct] N={value['n']}, Est. Mean={value['mean']:.2f}, Est. Median={value['median']:.2f}")
        elif value['type'] == 'Interpolated':
            print(f"- {key}: [Interpolated] Est. Mean={value['mean']:.2f}, Est. Median={value['median']:.2f}")
        else:
            print(f"- {key}: [{value['type']}] No estimate possible.")

    print("\nNote: [Direct] estimates use data where SS=100. [Interpolated] estimates use data from nearest SS above/below 100.")
    print("Compare these to the actual population medians shown on the graphs.")

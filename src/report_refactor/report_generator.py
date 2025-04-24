import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, BaseDocTemplate, PageTemplate, Frame
from io import BytesIO
from asrs_dsm_mapper import create_asrs_dsm_section
from reportlab.lib.units import mm, inch
import sqlite3
import pandas as pd
import os
from scipy import stats
import seaborn as sns
from collections import defaultdict
import logging
import json

# Set up logging
logging.basicConfig(
    filename='report_generation.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # Overwrite existing log file
)

# --- Global Styles ---
# Create and configure styles once at the module level
def get_styles():
    """Get the stylesheet with custom styles added."""
    styles = getSampleStyleSheet()
    # Add new smaller styles
    styles.add(ParagraphStyle(name='NormalSmall', parent=styles['Normal'], fontSize=9, leading=11))
    styles.add(ParagraphStyle(name='ItalicSmall', parent=styles['Italic'], fontSize=9, leading=11, fontName='Helvetica-Oblique'))
    styles.add(ParagraphStyle(name='HeaderSmall', parent=styles['Heading2'], fontSize=10, leading=12, fontName='Helvetica-Bold'))
    return styles
# --- End Global Styles ---

# Constants for ReportLab units
cm = 2.54  # 1 inch = 2.54 cm
inch = 72  # 1 inch = 72 points
mm = 72 / 25.4  # 1 mm = 72/25.4 points

# Estimated Normative Medians (Raw Score corresponding to SS=100)
# Derived from estimate_normative_means.py script
ESTIMATED_NORMATIVE_MEDIANS = {
    # Shifting Attention Test
    "Correct Reaction Time": 980.00,
    "Errors": 5.00,
    # Stroop Test
    "Reaction Time Correct": 631.50,
    "Commission Errors": 1.00, # Interpolated
    # Reasoning
    "Average Correct Reaction Time": 4869.00,
    "Reasoning Commission Errors": 4.00, # Specific key for component
    "Reasoning Omission Errors": 1.40, # Specific key for component (Interpolated)
    # Combined Reasoning Error (Calculated below where needed)
}

# --- Speed Accuracy Page Configuration ---
TEST_CONFIG_SPEED_ACCURACY = [
    {
        "db_test_name": "Shifting Attention Test",
        "cache_key": "shifting_attention_test",
        "speed_metric": "Correct Reaction Time",
        "error_metric": "Errors",
        "speed_label": "Reaction Time (Lower=Faster)",
        "error_label": "Errors (Higher=Worse)",
        "chart_title": "SAT: Speed vs Accuracy"
    },
    {
        "db_test_name": "Stroop Test",
        "cache_key": "stroop_test",
        "speed_metric": "Reaction Time Correct", 
        "error_metric": "Commission Errors",
        "speed_label": "Reaction Time (Lower=Faster)",
        "error_label": "Commission Errors (Higher=Worse)",
        "chart_title": "Stroop: Speed vs Accuracy"
    },
    {
        "db_test_name": "Reasoning",
        "cache_key": "reasoning",
        "speed_metric": "Average Correct Reaction Time", 
        "error_metric": ["Commission Errors", "Omission Errors"], # Sum these errors
        "speed_label": "Reaction Time (Lower=Faster)",
        "error_label": "Total Errors (Higher=Worse)",
        "chart_title": "Reasoning: Speed vs Accuracy"
    },
]
CACHE_DIR_SPEED_ACCURACY = os.path.join('data', 'analysis_output', 'cached_data')
# --- End Speed Accuracy Page Configuration ---

def get_patient_test_scores(patient_id, test_config, db_path='cognitive_analysis.db'):
    """Fetches a patient's raw speed and error scores for a specific test."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        test_name = test_config['db_test_name']
        speed_metric = test_config['speed_metric']
        error_metric = test_config['error_metric']

        # Fetch speed score
        speed_query = """
            SELECT score FROM subtest_results 
            WHERE patient_id = ? AND subtest_name LIKE ? AND metric LIKE ?
        """
        cursor.execute(speed_query, (patient_id, f'%{test_name}%', f'%{speed_metric}%'))
        speed_result = cursor.fetchone()
        patient_speed = float(speed_result[0]) if speed_result else None

        # Fetch error score(s)
        patient_error = None
        if isinstance(error_metric, str):
            error_query = """
                SELECT score FROM subtest_results 
                WHERE patient_id = ? AND subtest_name LIKE ? AND metric LIKE ?
            """
            cursor.execute(error_query, (patient_id, f'%{test_name}%', f'%{error_metric}%'))
            error_result = cursor.fetchone()
            patient_error = float(error_result[0]) if error_result else None
        else: # List of error metrics to sum
            total_error = 0
            found_any_error = False
            for err_metric in error_metric:
                error_query = """
                    SELECT score FROM subtest_results 
                    WHERE patient_id = ? AND subtest_name LIKE ? AND metric LIKE ?
                """
                cursor.execute(error_query, (patient_id, f'%{test_name}%', f'%{err_metric}%'))
                error_result = cursor.fetchone()
                if error_result:
                    try:
                        total_error += float(error_result[0])
                        found_any_error = True
                    except (ValueError, TypeError):
                        logging.warning(f"Invalid error score found for patient {patient_id}, test {test_name}, metric {err_metric}")
                        pass # Skip this metric if score is invalid
            if found_any_error:
                patient_error = total_error

        if patient_speed is not None and patient_error is not None:
            logging.info(f"Patient {patient_id} scores for {test_name}: Speed={patient_speed}, Error={patient_error}")
            return patient_speed, patient_error
        else:
            logging.warning(f"Could not find complete scores for patient {patient_id} on {test_name}")
            return None, None

    except Exception as e:
        logging.error(f"Error fetching patient {patient_id} scores for {test_config['db_test_name']}: {e}")
        return None, None
    finally:
        if conn:
            conn.close()

def plot_individual_on_population(patient_speed, patient_error, test_config):
    """Generates a speed-accuracy plot highlighting the patient's position."""
    cache_key = test_config['cache_key']
    population_cache_file = os.path.join(CACHE_DIR_SPEED_ACCURACY, f'{cache_key}_population_data.csv')
    regression_cache_file = os.path.join(CACHE_DIR_SPEED_ACCURACY, f'{cache_key}_regression.json')

    # Load cached data
    try:
        population_df = pd.read_csv(population_cache_file)
        with open(regression_cache_file, 'r') as f:
            regression_params = json.load(f)
    except FileNotFoundError:
        logging.error(f"Cache files not found for {cache_key}. Run speed_accuracy_analysis.py first.")
        return None
    except Exception as e:
        logging.error(f"Error loading cache files for {cache_key}: {e}")
        return None

    # Clean population data (ensure numeric, handle NaNs)
    try:
        population_df['speed_score'] = pd.to_numeric(population_df['speed_score'], errors='coerce')
        population_df['error_score'] = pd.to_numeric(population_df['error_score'], errors='coerce')
        population_df = population_df.dropna(subset=['speed_score', 'error_score'])
        # Optional: Apply outlier removal if consistent with analysis script
        # ... (add outlier removal logic if needed)
    except Exception as e:
        logging.error(f"Error cleaning population data for {cache_key}: {e}")
        return None
        
    if population_df.empty:
        logging.warning(f"Cleaned population data is empty for {cache_key}.")
        return None

    # Calculate axis limits with padding
    x_data = population_df['speed_score']
    y_data = population_df['error_score']
    x_min, x_max = x_data.min(), x_data.max()
    y_min, y_max = y_data.min(), y_data.max()

    x_range = x_max - x_min
    y_range = y_max - y_min

    # Add padding (e.g., 15% of the range)
    x_pad = x_range * 0.15
    y_pad = y_range * 0.15

    # Ensure padding is not zero if range is zero
    x_pad = x_pad if x_pad > 0 else 1 
    y_pad = y_pad if y_pad > 0 else 1

    final_x_min = x_min - x_pad
    final_x_max = x_max + x_pad
    final_y_min = y_min - y_pad
    final_y_max = y_max + y_pad

    # Calculate medians for quadrant lines
    x_median = x_data.median()
    y_median = y_data.median()

    # Get estimated normative medians (from SS=100)
    speed_metric_key = test_config.get('speed_metric')
    error_metric_key = test_config.get('error_metric')

    est_x_median = ESTIMATED_NORMATIVE_MEDIANS.get(speed_metric_key)
    est_y_median = None
    # Check if it's the specific list used for Reasoning errors
    if isinstance(error_metric_key, list) and error_metric_key == ["Commission Errors", "Omission Errors"]:
        comm_err_est = ESTIMATED_NORMATIVE_MEDIANS.get("Reasoning Commission Errors")
        omis_err_est = ESTIMATED_NORMATIVE_MEDIANS.get("Reasoning Omission Errors")
        if comm_err_est is not None and omis_err_est is not None:
            est_y_median = comm_err_est + omis_err_est
    else:
        # Otherwise, it should be a hashable type (string)
        est_y_median = ESTIMATED_NORMATIVE_MEDIANS.get(error_metric_key)

    # Generate the plot
    try:
        plt.figure(figsize=(8, 6)) # Adjusted size for report page
        
        # Plot population data points
        plt.scatter(population_df['speed_score'], population_df['error_score'], color='gray', alpha=0.3, s=30, label='Population')
        
        # Plot regression line
        slope = regression_params['slope']
        intercept = regression_params['intercept']
        x_line = np.linspace(x_min, x_max, 100)
        y_line = slope * x_line + intercept
        plt.plot(x_line, y_line, color='red', linewidth=2, label='Population Trend')

        # Add median lines for quadrants - from population data
        plt.axvline(x_median, color='grey', linestyle='--', linewidth=1, alpha=0.7, label=f'Pop. Median Speed ({x_median:.1f})')
        plt.axhline(y_median, color='grey', linestyle='--', linewidth=1, alpha=0.7, label=f'Pop. Median Error ({y_median:.1f})')

        # Add estimated normative median lines (SS=100)
        if est_x_median is not None:
            plt.axvline(est_x_median, color='blue', linestyle=':', linewidth=1.5, alpha=0.7, label=f'Norm Median Speed ({est_x_median:.1f})')
        if est_y_median is not None:
            plt.axhline(est_y_median, color='blue', linestyle=':', linewidth=1.5, alpha=0.7, label=f'Norm Median Error ({est_y_median:.1f})')

        # Highlight patient's position
        if patient_speed is not None and patient_error is not None:
            plt.scatter(patient_speed, patient_error, color='blue', s=100, edgecolor='black', zorder=5, label='Patient')
            plt.annotate('Patient', (patient_speed, patient_error), textcoords="offset points", xytext=(0,10), ha='center', color='blue')
        else:
            logging.warning(f"Patient scores missing for {test_config['chart_title']}, not highlighting.")

        # Labels and Title
        corr = regression_params.get('corr', np.nan)
        p = regression_params.get('p', np.nan)
        n = regression_params.get('n', 'N/A')
        plt.title(f"{test_config['chart_title']}\nPopulation Spearman R={corr:.2f}, p={p:.3f}, N={n}", fontsize=10)
        plt.xlabel(test_config['speed_label'], fontsize=9)
        plt.ylabel(test_config['error_label'], fontsize=9)
        plt.xticks(fontsize=8)
        plt.yticks(fontsize=8)
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.xlim(final_x_min, final_x_max)
        plt.ylim(final_y_min, final_y_max)
        plt.tight_layout()

        # Save to BytesIO
        img_data = BytesIO()
        plt.savefig(img_data, format='png', dpi=150)
        img_data.seek(0)
        plt.close()
        
        logging.info(f"Generated speed-accuracy chart for {test_config['chart_title']}")
        return img_data

    except Exception as e:
        logging.error(f"Error generating plot for {test_config['chart_title']}: {e}")
        plt.close() # Ensure figure is closed on error
        return None

def create_speed_accuracy_page(patient_id, styles):
    """Creates the ReportLab flowables for the speed-accuracy tradeoff page."""
    elements = []
    elements.append(create_section_title("Speed vs. Accuracy Analysis"))
    elements.append(Spacer(1, 6*mm))
    elements.append(Paragraph(
        "The following charts illustrate the relationship between response speed and accuracy "
        "Each chart shows the overall ADHD patient population trend (grey dots and red line) "
        "and highlights this patient\'s performance (blue dot). This helps visualize the individual\'s "
        "speed-accuracy tradeoff strategy compared to others. Non clinical means are in blue (Norm)",
        styles['NormalSmall']
    ))
    elements.append(Spacer(1, 8*mm))

    # Store images to potentially arrange them side-by-side or in a grid
    image_elements = []
    
    for test_config in TEST_CONFIG_SPEED_ACCURACY:
        logging.info(f"Generating speed-accuracy plot for patient {patient_id}, test: {test_config['chart_title']}")
        
        # Get patient scores
        patient_speed, patient_error = get_patient_test_scores(patient_id, test_config)

        if patient_speed is None or patient_error is None:
            warning_text = f"Data not available for {test_config['chart_title']}"
            image_elements.append(Paragraph(f"<i>{warning_text}</i>", styles['ItalicSmall']))
            logging.warning(f"{warning_text} for patient {patient_id}")
            continue
        
        # Generate plot
        img_data = plot_individual_on_population(patient_speed, patient_error, test_config)
        
        if img_data:
            # Adjust size for 2x2 grid
            img = Image(img_data, width=A4[0]*0.4, height=A4[1]*0.25) 
            image_elements.append(img)
        else:
            warning_text = f"Could not generate chart for {test_config['chart_title']}"
            image_elements.append(Paragraph(f"<i>{warning_text}</i>", styles['ItalicSmall']))
            logging.warning(f"{warning_text} for patient {patient_id}")
            
    # Add explanatory text to the 4th cell if needed
    if len(image_elements) == 3:
        explanation_text = """
        <b>Interpreting Speed-Accuracy Trends:</b><br/><br/>
        The population trend lines (red) illustrate how speed (reaction time) typically relates to accuracy (errors) for each test within the dataset.<br/><br/>
        &#8226; <b>Shifting Attention Test (SAT):</b> Shows a positive correlation, indicating a classic speed-accuracy tradeoff where faster responses tend to be associated with more errors.<br/><br/>
        &#8226; <b>Stroop Test & Reasoning:</b> These tests display a negative correlation. Slower reaction times are generally associated with <i>fewer</i> errors. This suggests that individuals who take more time tend to perform more accurately on these specific tasks within this population sample.
        """
        explanation_paragraph = Paragraph(explanation_text, styles['NormalSmall']) # Use a slightly smaller font
        image_elements.append(explanation_paragraph)
    elif len(image_elements) < 3: # Handle cases with even fewer graphs (though unlikely now)
        while len(image_elements) < 4:
            image_elements.append(Spacer(0, 0)) # Fill remaining with spacers
         
    # Arrange images in a 2x2 grid using a Table
    grid_data = [
        [image_elements[0], image_elements[1]],
        [image_elements[2], image_elements[3]] 
    ]
    
    # Create the table, adjust colWidths/rowHeights as needed
    grid_table = Table(grid_data, colWidths=[A4[0]*0.45] * 2) # Approx 45% width per col
    grid_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6*mm), # Space below rows
    ]))
    
    elements.append(grid_table)
         
    elements.append(PageBreak())
    return elements

def debug_log(message):
    """Log debug message to file and print to console"""
    logging.debug(message)
    print(message)

#python generate_report.py 34766-20231015201357.pdf --import

def create_radar_chart(scores, invalid_domains=None):
    """
    Create a radar chart of cognitive scores.
    
    Args:
        scores: Dict mapping domain names to scores
        invalid_domains: List of domain names that are invalid
    """
    try:
        if invalid_domains is None:
            invalid_domains = []
            
        # New domain order with correlations noted in comments
        labels = [
            "Executive Function",                # 1
            "Complex Attention",                 # 2 (Correlation with 1: 0.72)
            "Simple Attention",                  # 3 (Correlation with 2: 0.61)
            "Sustained Attention",               # 4 (Correlation with 2: 0.41, with 3: 0.36)
            "Processing Speed",                  # 5 (Correlation with 1: 0.50, with 4: 0.40)
            "Reaction Time",                     # 6 (Correlation with 5: 0.66)
            "Psychomotor Speed",                 # 7 (Correlation with 5: 0.68, with 6: 0.47)
            "Motor Speed",                       # 8 (Correlation with 7: 0.88)
            "Visual Memory",                     # 9 (Weak links to neighbours, placed here to group Memory)
            "Verbal Memory",                     # 10 (Grouped with Visual/Working)
            "Working Memory",                    # 11 (Correlation with 10: 0.91)
            "Reasoning",                         # 12 (Low overall correlations, placed near end)
            "Cognitive Flexibility"              # 13 (Correlation with 1: 0.99 - wrap-around. Correlation with 12: 0.21)
        ]
        
        # Define domain groups for symptom annotations
        domain_groups = {
            "Higher-Order Attention/Executive": [0, 1, 2, 3],  # Indices for Executive Function, Complex Attention, Simple Attention, Sustained Attention
            "Speed": [4, 5, 6, 7],  # Indices for Processing Speed, Reaction Time, Psychomotor Speed, Motor Speed
            "Memory": [8, 9, 10],  # Indices for Visual Memory, Verbal Memory, Working Memory
            "Flexibility/Reasoning": [11, 12]  # Indices for Reasoning, Cognitive Flexibility
        }
        
        # Define symptom annotations for each group
        symptom_annotations = {
            "Higher-Order Attention/Executive": "Difficulty Sustaining\nAttention (1b/A2)",
            "Speed": "Fidgeting (2a/B1)",
            "Memory": "Difficulty Waiting\nTurn (2h/B8)",
            "Flexibility/Reasoning": "Distractibility (1h/A8)"
        }
        
        # Log the scores we have
        logging.debug("\nScores passed to radar chart:")
        for label in labels:
            value = scores.get(label, "MISSING")
            logging.debug(f"  {label}: {value}")
            print(f"  {label}: {value}")
        
        # Check for missing domains and set to 0 with a warning
        values = []
        for label in labels:
            if label in scores:
                values.append(scores[label])
            else:
                logging.warning(f"Missing score for domain: {label} - using 0")
                print(f"[WARN] Missing score for domain: {label} - using 0")
                values.append(0)
                
        values += values[:1]  # loop closure
        
        # Create a mask for invalid domains
        invalid_mask = [label in invalid_domains for label in labels]
        invalid_mask += invalid_mask[:1]  # loop closure

        # Create figure with larger size to accommodate more domains
        fig, ax = plt.subplots(figsize=(14, 14), subplot_kw=dict(polar=True))
        ax.set_theta_offset(np.pi / 2)  # Top = 12 o'clock
        ax.set_theta_direction(-1)      # Clockwise

        # Draw colored background bands for standard deviation bands
        bands = [2, 9, 25, 75, 101]  # very low, low, low average, average, above average
        colors_band = ['#ff9999', '#ffcc99', '#ffff99', '#ccffcc', '#b3e6b3']

        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        angles += angles[:1]
        
        # Set x-ticks to match our angles
        ax.set_xticks(angles[:-1])

        for i in range(len(bands)-1):
            ax.fill_between(angles, bands[i], bands[i+1], color=colors_band[i], alpha=0.5)

        # Plot the data points
        ax.plot(angles, values, color='black', linewidth=2)
        ax.fill(angles, values, color='deepskyblue', alpha=0.6)
        
        # Mark invalid domains with red X
        for i, (angle, value, is_invalid) in enumerate(zip(angles[:-1], values[:-1], invalid_mask[:-1])):
            if is_invalid:
                # Plot a red X over invalid points
                marker_size = 200
                ax.scatter(angle, value, s=marker_size, color='red', marker='x', linewidth=2)
        
        # Calculate positions for labels and scores based on the number of domains
        # We need to distribute labels evenly around the circle
        num_domains = len(labels)
        
        # Add labels and scores outside the plot
        for i, (angle, value, label, is_invalid) in enumerate(zip(angles[:-1], values[:-1], labels, invalid_mask[:-1])):
            # Convert angle to degrees for easier handling
            deg_angle = np.degrees(angle)
            
            # Calculate positions using trigonometry
            # Note: We need to adjust the angle because 0 is at the right (east) in trig functions
            # but we want 0 to be at the top (north)
            adjusted_angle = np.radians(90 - deg_angle)
            
            # Use fixed radius for consistent label positioning
            label_radius = 0.46  # Fixed radius for all labels
            label_x = 0.5 + label_radius * np.cos(adjusted_angle)
            label_y = 0.5 + label_radius * np.sin(adjusted_angle)
            
            # Calculate score position - closer to the data point than the label
            score_radius = 0.38  # Fixed radius for all scores
            score_x = 0.5 + score_radius * np.cos(adjusted_angle)
            score_y = 0.5 + score_radius * np.sin(adjusted_angle)
            
            # Format the label for better display
            display_label = label
            if ' ' in label:
                # Special handling for Executive Function to ensure it's visible
                if label == "Executive Function":
                    display_label = "Executive\nFunction"
                else:
                    display_label = label.replace(' ', '\n')
                
            # Mark invalid domains in the label with (INVALID)
            if is_invalid:
                display_label = display_label + "\n(INVALID)"
            
            # Use figure coordinates for precise placement
            # Increase font size for better readability
            ax.annotate(display_label, xy=(label_x, label_y), xycoords='figure fraction',
                       ha='center', va='center', fontsize=12, weight='bold')
            
            # Add the score near the data point
            score_text = f"{value}"
            
            ax.annotate(score_text, xy=(score_x, score_y), xycoords='figure fraction',
                       ha='center', va='center', fontsize=13,
                       bbox=dict(boxstyle="round,pad=0.2", fc='white', ec="gray", alpha=0.9))
        
        # Add symptom annotations for each domain group
        for group_name, domain_indices in domain_groups.items():
            # Calculate the average angle for this group
            group_angles = [angles[i] for i in domain_indices]
            avg_angle = sum(group_angles) / len(group_angles)
            
            # Calculate the position for the symptom annotation
            # Place it inside the chart but not too close to center
            annotation_radius = 30  # Place at 30 percentile mark
            
            # Convert to figure coordinates
            adjusted_angle = np.radians(90 - np.degrees(avg_angle))
            annotation_x = 0.5 + 0.2 * np.cos(adjusted_angle)  # 0.5 is center, 0.2 is radius
            annotation_y = 0.5 + 0.2 * np.sin(adjusted_angle)
            
            # Add the symptom annotation with a colored background
            symptom_text = symptom_annotations[group_name]
            
            # Use different colors for each group
            group_colors = {
                "Higher-Order Attention/Executive": "#FFD700",  # Gold
                "Speed": "#FF6347",                            # Tomato
                "Memory": "#4682B4",                           # Steel Blue
                "Flexibility/Reasoning": "#32CD32"             # Lime Green
            }
            
            ax.annotate(symptom_text, xy=(annotation_x, annotation_y), xycoords='figure fraction',
                       ha='center', va='center', fontsize=12, weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", fc=group_colors[group_name], ec="gray", alpha=0.7))
        
        # Set y-limits and grid
        ax.set_ylim(0, 100)
        ax.set_yticks([2, 9, 25, 75])
        ax.set_yticklabels([])  # Hide numeric labels
        ax.grid(True, alpha=0.3)
        
        # Remove the axis labels and ticks
        ax.set_xticklabels([])
        
        # Create handles for the legend
        handles = []
        for i, (band, color) in enumerate(zip(["Very low (≤ 2%)", "Low (2-9%)", "Low average (9-25%)", "Average (25-75%)", "Above average (> 75%)"], colors_band)):
            patch = plt.Rectangle((0, 0), 1, 1, color=color, alpha=0.5)
            handles.append(patch)
            
        # Add markers for valid and invalid scores
        valid_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='black',
                                  markersize=10, label='Valid Score', linewidth=0)
        handles.append(valid_marker)
        
        if any(invalid_mask):
            invalid_marker = plt.Line2D([0], [0], marker='x', color='w', markerfacecolor='red',
                                   markersize=10, label='Invalid Score', linewidth=0)
            handles.append(invalid_marker)
        
        # Create a separate figure for the legend only
        legend_fig, legend_ax = plt.subplots(figsize=(14, 1.5))
        legend_ax.axis('off')  # Hide axes
        
        # Add the legend to this figure with clear labels
        legend_labels = ["Very low (≤ 2%)", "Low (2-9%)", "Low average (9-25%)", "Average (25-75%)", "Above average (> 75%)", "Valid Score"]
        if any(invalid_mask):
            legend_labels.append("Invalid Score")
            
        legend = legend_ax.legend(handles=handles, loc='center', ncol=len(legend_labels), 
                                 labels=legend_labels, fontsize=12,
                                 frameon=True, framealpha=0.8)
        
        # Save the legend figure to BytesIO
        legend_buffer = BytesIO()
        plt.savefig(legend_buffer, format='png', dpi=150, bbox_inches='tight')
        plt.close(legend_fig)
        
        # Save the main radar chart to BytesIO
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', pad_inches=0.5)
        plt.close(fig)
        
        # Return both the main chart and the legend
        return buffer, legend_buffer
        
    except Exception as e:
        # Log the error and return a placeholder image
        error_msg = f"Error creating radar chart: {str(e)}"
        logging.error(error_msg)
        print(f"[ERROR] {error_msg}")
        
        # Create a simple error message image
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, f"Error creating radar chart:\n{str(e)}", 
                ha='center', va='center', fontsize=12)
        ax.axis('off')
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        buffer.seek(0)
        plt.close()
        
        return buffer, buffer

from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

def create_npq_section(data):
    from collections import defaultdict
    elements = []
    styles = get_styles()

    npq_scores = data.get("npq_scores", [])
    npq_questions = data.get("npq_questions", [])

    if not npq_scores:
        return []

    def severity_color(severity):
        s = severity.lower()
        if s == "severe":
            return colors.red
        elif s == "moderate":
            return colors.orange
        elif s == "mild":
            return colors.yellow
        return colors.whitesmoke

    def section_block(title, domains):
        # Make section headers more distinct
        header = f"=== {title} Symptoms ==="
        rows = [(header,)]  # Section header with clear formatting
        for domain in domains:
            for row in npq_scores:
                if row[1].lower() == domain.lower():
                    score = row[2]
                    severity = row[3]
                    color = severity_color(severity)
                    rows.append((domain, score, severity))
                    break
        return rows

    # Section heading + disclaimer
    elements.append(create_section_title("NPQ LF-207 Diagnostic Screen"))
    disclaimer = ("<i>The NPQ is a clinical screening tool. Scores suggest potential symptom burden and are not diagnostic. "
                  "Results should be used as a basis for clinical enquiry rather than diagnosis. "
                  "Clinicians should use these results to guide further assessment and corroborate with clinical judgment.</i>")
    elements.append(Paragraph(disclaimer, styles["Normal"]))
    elements.append(Spacer(1, 12))

    full_table = []

    # Section blocks organized as requested with consistent domain groupings
    full_table += section_block("Attention & Hyperactivity", ["ADHD", "Attention", "Impulsive", "Learning", "Memory", "Fatigue", "Sleep"])
    full_table += section_block("Anxiety", ["Anxiety", "Panic", "Agoraphobia", "Obsessions & Compulsions", "Social Anxiety", "PTSD"])
    full_table += section_block("Mood", ["Depression", "Bipolar", "Mood Stability", "Mania", "Aggression"])
    full_table += section_block("Autism Spectrum", ["Autism", "Asperger's"])
    full_table += section_block("Other Concerns", ["Psychotic", "Somatic", "Fatigue", "Suicide", "Pain", "Substance Abuse", "MCI", "Concussion"])

    # Render grouped table
    table_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),  # Smaller font size
        ('LEFTPADDING', (0,0), (-1,-1), 3),  # Reduced padding
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ])

    # Add color rows with enhanced section header styling
    row_idx = 0
    for row in full_table:
        if len(row) == 3:  # Data row
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), severity_color(row[2]))
        elif len(row) == 1:  # Section header
            table_style.add('SPAN', (0, row_idx), (-1, row_idx))
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#2F4F4F'))  # Dark slate gray
            table_style.add('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.white)
            table_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
            table_style.add('ALIGN', (0, row_idx), (-1, row_idx), 'CENTER')
        row_idx += 1

    # Adjusted column widths for 3 columns
    table = Table(full_table, colWidths=[250, 100, 150])
    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 10))  # Reduced spacing

    # Color legend
    legend_data = [
        ["Severity Color Legend"],
        ["Severe", "Moderate", "Mild", "None"]
    ]
    legend_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('SPAN', (0,0), (-1,0)),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),  # Make header bold
        ('BACKGROUND', (0,1), (0,1), colors.red),
        ('BACKGROUND', (1,1), (1,1), colors.orange),
        ('BACKGROUND', (2,1), (2,1), colors.yellow),
        ('BACKGROUND', (3,1), (3,1), colors.whitesmoke),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 8),  # Smaller font size
        ('LEFTPADDING', (0,0), (-1,-1), 3),  # Reduced padding
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ])
    legend_table = Table(legend_data, colWidths=[125, 125, 125, 125])
    legend_table.setStyle(legend_style)
    elements.append(legend_table)
    elements.append(Spacer(1, 10))  # Reduced spacing

    # Full Response Table - using npq_questions instead of npq_responses
    if npq_questions:
        elements.append(create_section_title("Detailed NPQ Responses"))
        
        # Group questions by domain for better organization
        grouped = defaultdict(list)
        domain_severities = {}  # Track overall severity for each domain
        
        for q in npq_questions:
            domain = q[2]
            question_text = q[4]
            score = q[5]
            severity = q[6]
            grouped[domain].append((question_text, score, severity))
            
            # Update domain severity (prioritize most severe)
            current_severity = domain_severities.get(domain, 'none')
            severity_rank = {
                'severe': 3,
                'moderate': 2,
                'mild': 1,
                'none': 0
            }
            if severity_rank.get(severity.lower(), 0) > severity_rank.get(current_severity, 0):
                domain_severities[domain] = severity.lower()
        
        # Sort domains alphabetically for consistent presentation
        domains = sorted(grouped.keys())
        
        # Create table with headers
        response_rows = [("Question", "Score", "Severity")]
        
        # Add each domain and its questions
        for domain in domains:
            # Add domain header
            response_rows.append((domain, '', ''))
            
            # Sort questions by severity (severe to mild)
            questions = sorted(grouped[domain], key=lambda x: {
                'severe': 0,
                'moderate': 1,
                'mild': 2
            }.get(x[2].lower(), 3))
            
            # Add questions for this domain
            for q in questions:
                response_rows.append(q)

        # Create and style the table
        response_table_style = TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),  # Make header bold
            ('FONTSIZE', (0,0), (-1,-1), 8),  # Smaller font size
            ('LEFTPADDING', (0,0), (-1,-1), 3),  # Reduced padding
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('BACKGROUND', (0,0), (-1,0), colors.grey),  # Header row background
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),  # Header row text color
        ])

        # Add color rows with enhanced section header styling
        row_idx = 0
        for row in response_rows:
            if row[1] == '' and row[2] == '':  # Domain header
                domain = row[0]
                response_table_style.add('SPAN', (0, row_idx), (-1, row_idx))
                # Color domain header based on its overall severity
                header_color = severity_color(domain_severities.get(domain, 'none'))
                response_table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), header_color)
                # Ensure text is readable on any background
                text_color = colors.white if domain_severities.get(domain, 'none') in ['severe', 'moderate'] else colors.black
                response_table_style.add('TEXTCOLOR', (0, row_idx), (-1, row_idx), text_color)
                response_table_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
                response_table_style.add('ALIGN', (0, row_idx), (-1, row_idx), 'CENTER')
            elif row[2] and row[0] != "Question":  # Data row (not header)
                response_table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), severity_color(row[2]))
            row_idx += 1

        # Adjusted column widths for better readability
        response_table = Table(response_rows, colWidths=[350, 50, 100], repeatRows=1)  # Repeat header row
        response_table_style.add('FONTSIZE', (0,0), (-1,-1), 8)  # Smaller font size
        response_table_style.add('LEFTPADDING', (0,0), (-1,-1), 3)  # Reduced padding
        response_table_style.add('RIGHTPADDING', (0,0), (-1,-1), 3)
        response_table_style.add('TOPPADDING', (0,0), (-1,-1), 3)
        response_table_style.add('BOTTOMPADDING', (0,0), (-1,-1), 3)
        response_table.setStyle(response_table_style)
        elements.append(response_table)
        elements.append(Spacer(1, 6))  # Reduced spacing

    return elements


def draw_logo(canvas, doc):
    logo_path = "imgs/LogoWB.png"
    # Reduce logo size from 40mm to 25mm (about 37.5% smaller)
    logo_width = 20 * mm
    logo_height = 20 * mm
    # Adjust position to keep it in the corner but with a bit more margin
    x = doc.pagesize[0] - logo_width - 10  # right margin (reduced from 20)
    y = doc.pagesize[1] - logo_height - 10  # top margin (reduced from 20)
    canvas.drawImage(logo_path, x, y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')


def create_section_title(title):
    return Paragraph(f'<b>{title}</b>', get_styles()['Heading2'])


def color_for_percentile(p):
    if p is None:
        return colors.lightgrey
    if p > 74:
        return colors.green
    elif 25 <= p <= 74:
        return colors.lightgreen
    elif 9 <= p < 25:
        return colors.khaki
    elif 2 <= p < 9:
        return colors.orange
    else:
        return colors.red


def get_percentile_color(percentile):
    if percentile is None or percentile == "":
        return colors.white
    try:
        percentile = float(percentile)
        if percentile > 75:
            return colors.HexColor('#b3e6b3')  # Above average (> 75)
        elif percentile >= 25:
            return colors.HexColor('#ccffcc')  # Average (25-75)
        elif percentile >= 9:
            return colors.HexColor('#ffff99')  # Low average (9-25)
        elif percentile >= 2:
            return colors.HexColor('#ffcc99')  # Low (2-9)
        else:
            return colors.HexColor('#ff9999')  # Very low (≤ 2)
    except (ValueError, TypeError):
        return colors.white


def create_fancy_report(data, output_path):
    def adjust_canvas(canvas, doc):
        draw_logo(canvas, doc)

    # Use BaseDocTemplate instead of SimpleDocTemplate
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=0.3 * inch,
        rightMargin=0.3 * inch,
        topMargin=0.3 * inch,
        bottomMargin=0.5 * inch # Increased bottom margin slightly for footer
    )

    # Define the main frame, reducing height to accommodate potential header/footer space
    # Adjusted height calculation to account for bottom margin and footer space
    frame_height = doc.height - (15 * mm) # Reserve space for footer/header
    frame = Frame(
        doc.leftMargin, 
        doc.bottomMargin + 5 * mm,  # Move content up by reducing bottom position 
        doc.width, 
        frame_height - 5 * mm,  # Adjust height accordingly
        id='normal'
    )

    # Add PageTemplate with the footer function
    doc.addPageTemplates([
        PageTemplate(id='AllPages', frames=frame, onPage=lambda c, d: footer(c, d, data["patient"]), onPageEnd=adjust_canvas)
    ])

    # Get styles with custom styles already added
    styles = get_styles()
    
    elements = []
    # Heading centered
    heading_text = "Cognitive Profile and ADHD Assessment for Adults"
    #heading_text = "Cognitive Profile and ADHD Assessment for Adults: Neurocognitive Domains and DSM-5-Aligned ADHD Diagnostic Indicators"
    
    # Create a custom heading style with better centering properties
    heading_style = ParagraphStyle(
        name='CenteredHeading',
        parent=styles["Heading1"],
        alignment=1,  # 1 = center alignment
        spaceAfter=6  # Reduce space after the heading
    )
    
    heading_para = Paragraph(f"<b>{heading_text}</b>", heading_style)

    # Wrap in a table with full page width to enable proper centering
    heading_table = Table([[heading_para]], colWidths=[doc.width * 0.9])  # 90% of page width
    heading_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),  # Remove padding to improve centering
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements.append(heading_table)
    elements.append(Spacer(1, 12))  # Reduced from 24 to move content up

    # Demographics aligned left
    demo_box = []
    demo_box.append(Paragraph("<b>Demographics</b>", styles['Heading2']))

    patient = data["patient"]
    demographics = f"Patient ID: {patient[0]}<br/>Age: {patient[2]}<br/>Language: {patient[3]}<br/>Test Date: {patient[1]}"
    demo_box.append(Paragraph(demographics, styles['Normal']))
    elements.extend(demo_box)
    elements.append(Spacer(1, 18))

    # Validity Check
    invalid_scores = [s for s in data["cognitive_scores"] if s[6] and str(s[6]).lower() == 'no']
    missing_validity = [s for s in data["cognitive_scores"] if not s[6]]

    if invalid_scores:
        elements.append(create_section_title("Validity Check"))
        elements.append(Paragraph("<font color='red'>Warning: Some cognitive tests failed validity checks.</font>", styles['Normal']))
        for s in invalid_scores:
            elements.append(Paragraph(f"Invalid domain: {s[2]}", styles['Normal']))
        elements.append(Spacer(1, 12))

    if missing_validity:
        elements.append(create_section_title("Missing Validity Data"))
        elements.append(Paragraph("<font color='orange'>Warning: Some tests are missing validity index data.</font>", styles['Normal']))
        for s in missing_validity:
            elements.append(Paragraph(f"No validity index: {s[2]}", styles['Normal']))
        elements.append(Spacer(1, 12))

    # Get domain scores and invalid domains from cognitive_scores data
    domain_percentiles = {}
    invalid_domains = []
    
    # Create more flexible domain mappings to handle variations in domain names
    domain_mappings = {
        "Reaction Time": ["Reaction Time", "Reaction Time*", "Correct Reaction Time*"],
        "Complex Attention": ["Complex Attention", "Complex Attention*", "Sustained Attention"],
        "Cognitive Flexibility": ["Cognitive Flexibility", "Cognitive Flexibility*", "Shifting Attention Test (SAT)"]
    }
    
    # First pass: Extract all domains and check which are available
    available_domains = {}
    for s in data["cognitive_scores"]:
        domain_name, raw_score, std_score, percentile, validity_index = s[2], s[3], s[4], s[5], s[6]
        
        # Store all available domains for possible mapping
        try:
            if percentile is not None:
                available_domains[domain_name] = {
                    "percentile": int(percentile) if percentile not in (None, 'NA') else 0,
                    "valid": False if validity_index and validity_index.lower() == 'no' else True
                }
                debug_log(f"Found domain {domain_name} with percentile {percentile}")
            else:
                debug_log(f"Percentile is None for domain {domain_name}")
        except (ValueError, TypeError) as e:
            debug_log(f"Error processing percentile for {domain_name}: {e}")
    
    # Second pass: Map to standard domain names for the radar chart
    radar_domains = [
        "Executive Function",
        "Complex Attention",
        "Simple Attention",
        "Sustained Attention",
        "Processing Speed",
        "Reaction Time",
        "Psychomotor Speed",
        "Motor Speed",
        "Visual Memory",
        "Verbal Memory",
        "Working Memory",
        "Reasoning",
        "Cognitive Flexibility"
    ]
    
    for domain in radar_domains:
        # Direct match
        if domain in available_domains:
            domain_percentiles[domain] = available_domains[domain]["percentile"]
            if not available_domains[domain]["valid"]:
                invalid_domains.append(domain)
            continue
            
        # Check for alternate names if direct match not found
        mapped = False
        if domain in domain_mappings:
            for alt_name in domain_mappings[domain]:
                if alt_name in available_domains:
                    domain_percentiles[domain] = available_domains[alt_name]["percentile"]
                    if not available_domains[alt_name]["valid"]:
                        invalid_domains.append(domain)
                    mapped = True
                    debug_log(f"Mapped {alt_name} to standard domain {domain}")
                    break
        
        if not mapped:
            debug_log(f"No match found for domain {domain}")
    
    # Log domain scores for debugging
    debug_log("\nFinal domain scores for radar chart:")
    for domain in radar_domains:
        value = domain_percentiles.get(domain, "MISSING")
        valid = "INVALID" if domain in invalid_domains else "valid"
        debug_log(f"  {domain}: {value} ({valid})")
    
    # Radar Chart using the data we already have
    radar_img, legend_img = create_radar_chart(domain_percentiles, invalid_domains)
    elements.append(create_section_title("Cognitive Domain Profile"))
    elements.append(Spacer(1, 30))  # Increase vertical space from default
    elements.append(Image(radar_img, width=450, height=450))
    elements.append(Image(legend_img, width=450, height=50))
    elements.append(PageBreak())  # Add page break after radar chart

    # Cognitive Score Table
    if data["cognitive_scores"]:
        elements.append(create_section_title("Cognitive Domain Scores"))
        
        # Create table data
        score_data = [
            ["Domain", "Standard Score", "Percentile", "Classification", "Valid"],
        ]
        
        # Add domain scores
        table_styles = [
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')  # Make header bold
        ]
        
        # Add rows and apply color coding based on percentile
        row_idx = 1
        
        # Track if we've seen NCI to add it at the end
        nci_data = None
        
        for s in data["cognitive_scores"]:
            domain, raw, std, perc, valid = s[2], s[3], s[4], s[5], s[6]
            classification = ""
            
            # Determine classification based on percentile
            try:
                perc_float = float(perc)
                if perc_float > 75:
                    classification = "Above Average"
                elif perc_float >= 25:
                    classification = "Average"
                elif perc_float >= 9:
                    classification = "Low Average"
                elif perc_float >= 2:
                    classification = "Low"
                else:
                    classification = "Very Low"
            except (ValueError, TypeError):
                classification = "Unknown"
            
            # Save NCI for later
            if domain == "Neurocognitive Index":
                nci_data = [domain, std, perc, classification, valid]
                continue
                
            score_data.append([domain, std, perc, classification, valid])
            
            # Add color coding based on percentile value
            valid_str = str(valid).strip().lower()
            if valid_str in ['1', 'yes', 'valid', 'true']:
                bg_color = get_percentile_color(perc)
                table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
            
            row_idx += 1
        
        # Add NCI at the end if we found it
        if nci_data:
            score_data.append(nci_data)
            
            # Add color coding for NCI
            valid_str = str(nci_data[4]).strip().lower()
            if valid_str in ['1', 'yes', 'valid', 'true']:
                bg_color = get_percentile_color(nci_data[2])
                table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
            
            # Make NCI row bold
            table_styles.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            
        # Create the table
        score_table = Table(score_data, colWidths=[120, 100, 80, 100, 60])
        score_table.setStyle(TableStyle(table_styles))
        elements.append(score_table)
        elements.append(Spacer(1, 12))

    else:
        print("[WARN] No cognitive_scores found for patient")
        elements.append(Paragraph("Cognitive domain scores were not available.", styles['Normal']))
    
    # Add color legend for percentile ranges
    elements.append(create_section_title("Score Interpretation"))
    
    # Create a table with color bands and their interpretations
    legend_data = [
        ("Percentile Range", "Classification", "Clinical Interpretation"),
        ("> 75", "Above Average", "Strengths"),
        ("25-75", "Average", "Normal functioning"),
        ("9-25", "Low Average", "Mild difficulties"),
        ("2-9", "Low", "Significant difficulties"),
        ("≤ 2", "Very Low", "Severe impairment")
    ]
    
    # Set column widths
    legend_col_widths = [120, 120, 200]
    
    # Create table styles with appropriate colors matching the radar chart
    legend_styles = [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Make header bold
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        # Color bands matching radar chart
        ('BACKGROUND', (0, 1), (-1, 1), '#b3e6b3'),  # Above average (> 75)
        ('BACKGROUND', (0, 2), (-1, 2), '#ccffcc'),  # Average (25-75)
        ('BACKGROUND', (0, 3), (-1, 3), '#ffff99'),  # Low average (9-25)
        ('BACKGROUND', (0, 4), (-1, 4), '#ffcc99'),  # Low (2-9)
        ('BACKGROUND', (0, 5), (-1, 5), '#ff9999'),  # Very low (≤ 2)
    ]
    
    legend_table = Table(legend_data, colWidths=legend_col_widths)
    legend_table.setStyle(TableStyle(legend_styles))
    elements.append(legend_table)
    elements.append(Spacer(1, 18))

    # Subtest Results Table - Nested by test
    elements.append(create_section_title("Subtest Results"))
    if data["subtests"]:
        grouped = defaultdict(list)
        for row in data["subtests"]:
            # Extract data with the new schema (includes is_valid at row[7])
            subtest_name = row[2]
            metric = row[3]
            score = row[4]
            std_score = row[5]
            percentile = row[6]
            is_valid = row[7] if len(row) > 7 else 1  # Default to valid if column doesn't exist
            
            # Store validity with the test data
            grouped[subtest_name].append((metric, score, std_score, percentile, is_valid))

        table_data = []
        style = [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Make headers bold
        ]

        row_idx = 0
        for test_name, rows in grouped.items():
            # Check if any metrics in this test are invalid - is_valid is the 5th element (index 4)
            # Handle potential string representations of validity
            test_is_valid = all(str(is_valid).strip().lower() in ['1', 'yes', 'valid'] 
                                for _, _, _, _, is_valid in rows)
            
            # Test header row - mark invalid tests
            test_display_name = test_name
            if not test_is_valid:
                test_display_name += " (INVALID)"
                # Add red background for invalid tests
                style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightcoral))
            
            table_data.append([test_display_name])
            style.append(('SPAN', (0, row_idx), (-1, row_idx)))
            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            row_idx += 1

            # Column header
            table_data.append(['Metric', 'Score', 'Standard', 'Percentile'])
            style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.grey))
            style.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.whitesmoke))
            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            row_idx += 1

            # Subtest metrics
            for metric, score, std, perc, is_valid in rows:
                try:
                    perc = int(perc) if perc is not None else None
                    
                    # Add the row data
                    table_data.append([metric, score, std, perc])
                    
                    # Apply color coding based on percentile value
                    valid_str = str(is_valid).strip().lower()
                    if valid_str in ['1', 'yes', 'valid', 'true']:
                        bg_color = get_percentile_color(perc)
                        style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
                    elif is_valid == 0 or valid_str in ['0', 'no', 'false', 'invalid']:
                        style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightcoral))
                        
                except Exception as e:
                    print(f"[ERROR] Invalid percentile: {perc} for metric {metric}, error: {e}")
                    # Still add the row even if coloring fails
                    table_data.append([metric, score, std, perc])
                row_idx += 1

        # Set column widths to better fit the content
        col_widths = [180, 80, 100, 80]  # Match cognitive scores table
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle(style))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # --- Speed vs Accuracy Page ---
    logging.info(f"Creating speed vs accuracy page for patient {data['patient'][0]}")
    elements.append(PageBreak())  # Start Speed vs Accuracy on a new page
    elements.extend(create_speed_accuracy_page(data['patient'][0], styles))
    # --- End Speed vs Accuracy Page ---

    # --- ASRS/DSM Section ---
    logging.info("Creating ASRS/DSM section")
    # Fetch ASRS data similar to how NPQ data is fetched
    asrs_responses = {row[2]: row[4] for row in data["asrs"]}
    elements.extend(create_asrs_dsm_section(asrs_responses))

    # Add page break between ASRS and NPQ sections
    elements.append(PageBreak())

    #NPQ
    elements.extend(create_npq_section(data))

    # Domain Explanation Page
    elements.append(PageBreak())  # Start explanations on a new page
    domain_explanation_flowables = create_domain_explanation_page(styles)
    elements.extend(domain_explanation_flowables)
    elements.append(PageBreak())  # End explanations with a page break

    # Build the document - remove onFirstPage since we're using PageTemplate now
    doc.build(elements)

    print(f"[INFO] Report saved to {output_path}")


def create_sat_speed_accuracy_chart(patient_id, db_path='cognitive_analysis.db'):
    """
    Creates a personalized Shifting Attention Test (SAT) speed-accuracy tradeoff chart
    showing the population trend line and the patient's position.
    
    Args:
        patient_id: The ID of the patient
        db_path: Path to the database file
        
    Returns:
        BytesIO: A BytesIO object containing the plot image data
    """
    try:
        # Define cache directory and file
        cache_dir = os.path.join('data', 'analysis_output', 'cached_data')
        os.makedirs(cache_dir, exist_ok=True)
        population_cache_file = os.path.join(cache_dir, 'sat_rt_errors_population_data.csv')
        regression_cache_file = os.path.join(cache_dir, 'sat_rt_errors_regression.json')
        
        # Try to load population data from cache
        population_df = None
        regression_params = None
        
        # Load population data if it exists
        if os.path.exists(population_cache_file):
            print(f"Loading cached SAT population data from {population_cache_file}")
            try:
                population_df = pd.read_csv(population_cache_file)
                # === ADDED CHECK: Verify if current patient is in the loaded cache ===
                if population_df is not None and not population_df.empty:
                    if str(patient_id) not in population_df['patient_id'].astype(str).values:
                        print(f"Patient {patient_id} not found in cached data. Discarding cache and querying DB.")
                        population_df = None # Force fallback to DB query
                    else:
                        print(f"Patient {patient_id} found in cached data.")
                # =======================================================================
            except Exception as e:
                print(f"Error loading cached population data: {e}")
                population_df = None # Fallback to DB query on error
        
        # If not in cache OR patient wasn't found in cache, query from database
        if population_df is None:
            print("SAT population data not cached or incomplete for patient, querying database...")
            try:
                # Connect to the database
                conn = sqlite3.connect(db_path)
                
                # First, verify what data exists for this patient
                debug_query = """
                SELECT patient_id, subtest_name, metric, score, standard_score, percentile
                FROM subtest_results 
                WHERE patient_id = ? 
                AND subtest_name LIKE '%Shifting Attention Test%'
                """
                debug_df = pd.read_sql_query(debug_query, conn, params=(patient_id,))
                if not debug_df.empty:
                    print(f"Found SAT data for patient {patient_id}:")
                    print(debug_df)
                else:
                    print(f"No SAT data found for patient {patient_id} in debug query")
                
                # Get population data for the regression line - use more flexible matching
                query = """
                SELECT sr1.patient_id, sr1.standard_score as rt_score, sr2.standard_score as err_score
                FROM subtest_results sr1
                JOIN subtest_results sr2 ON sr1.patient_id = sr2.patient_id
                WHERE sr1.subtest_name LIKE '%Shifting Attention Test%'
                AND sr1.metric LIKE '%Correct Reaction Time%' 
                AND sr2.subtest_name LIKE '%Shifting Attention Test%'
                AND sr2.metric LIKE '%Errors%' 
                """
                population_df = pd.read_sql_query(query, conn)
                print(f"Found {len(population_df)} patients with SAT data for population analysis")
                
                # Check if our patient is in the results
                if str(patient_id) in population_df['patient_id'].astype(str).values:
                    print(f"Patient {patient_id} is in the population dataset")
                else:
                    print(f"Patient {patient_id} NOT found in population dataset. Available IDs: {population_df['patient_id'].unique()[:5]}...")
                
                conn.close()
                
                # Save population data to cache
                if not population_df.empty:
                    print(f"Saving population data to cache: {population_cache_file}")
                    try:
                        population_df.to_csv(population_cache_file, index=False)
                    except Exception as e:
                        print(f"Error saving population data to cache: {e}")
            except Exception as e:
                print(f"Error querying database for SAT data: {e}")
                return None
            
        if population_df is None or population_df.empty:
            print(f"No SAT data found in the database or cache")
            return None
        
        # Get the specific patient's data
        try:
            # Convert patient_id to string for matching
            str_patient_id = str(patient_id)
            # Make matching more robust by comparing string versions
            patient_data = population_df[population_df['patient_id'].astype(str) == str_patient_id]
            
            if patient_data.empty:
                print(f"No SAT data found for patient ID {patient_id} in the processed dataset")
                print(f"Available patient IDs: {population_df['patient_id'].unique()[:5]}...")
                return None
            else:
                print(f"Found SAT data for patient {patient_id}: RT={patient_data['rt_score'].values[0]}, Errors={patient_data['err_score'].values[0]}")
        except Exception as e:
            print(f"Error filtering data for patient {patient_id}: {e}")
            return None
        
        # Convert to numeric and drop NaNs
        try:
            population_df['rt_score'] = pd.to_numeric(population_df['rt_score'], errors='coerce')
            population_df['err_score'] = pd.to_numeric(population_df['err_score'], errors='coerce')
            population_df = population_df.dropna(subset=['rt_score', 'err_score'])
            
            if len(population_df) < 10:
                print(f"Insufficient SAT data points after cleaning: {len(population_df)}")
                return None
        except Exception as e:
            print(f"Error converting data types: {e}")
            return None
        
        # Try to load regression parameters from cache
        if os.path.exists(regression_cache_file):
            print(f"Loading cached regression parameters from {regression_cache_file}")
            try:
                import json
                with open(regression_cache_file, 'r') as f:
                    regression_params = json.load(f)
                slope = regression_params['slope']
                intercept = regression_params['intercept']
                r_value = regression_params['r_value']
                p_value = regression_params['p_value']
                std_err = regression_params['std_err']
                corr = regression_params['corr']
                p = regression_params['p']
            except Exception as e:
                print(f"Error loading regression parameters: {e}")
                regression_params = None
        
        # Calculate regression if not in cache
        if regression_params is None:
            try:
                # Calculate and plot the regression line for the population
                slope, intercept, r_value, p_value, std_err = stats.linregress(
                    population_df['rt_score'], population_df['err_score'])
                
                # Calculate Spearman correlation
                corr, p = stats.spearmanr(population_df['rt_score'], population_df['err_score'])
                
                # Save regression parameters to cache
                regression_params = {
                    'slope': float(slope),
                    'intercept': float(intercept),
                    'r_value': float(r_value),
                    'p_value': float(p_value),
                    'std_err': float(std_err),
                    'corr': float(corr),
                    'p': float(p)
                }
                
                try:
                    import json
                    with open(regression_cache_file, 'w') as f:
                        json.dump(regression_params, f)
                    print(f"Saved regression parameters to cache: {regression_cache_file}")
                except Exception as e:
                    print(f"Error saving regression parameters: {e}")
            except Exception as e:
                print(f"Error calculating regression: {e}")
                return None
        
        try:
            # Generate x values across the range for the line
            x_min, x_max = population_df['rt_score'].min(), population_df['rt_score'].max()
            x_line = np.linspace(x_min, x_max, 100)
            y_line = slope * x_line + intercept
            
            # Plot regression line
            plt.plot(x_line, y_line, color='red', linewidth=2)
            
            # Add patient's point
            patient_rt = patient_data['rt_score'].values[0]
            patient_err = patient_data['err_score'].values[0]
            plt.scatter(patient_rt, patient_err, color='blue', s=100, marker='o', 
                        label=f'Patient {patient_id}')
            
            # Highlight patient position with a vertical and horizontal line to axes
            plt.axvline(x=patient_rt, color='blue', linestyle='--', alpha=0.5)
            plt.axhline(y=patient_err, color='blue', linestyle='--', alpha=0.5)
            
            # Clean labels and add interpretation notes
            rt_interp = "(Lower=Faster)"
            err_interp = "(Higher=More Errors)"
            
            plt.title(f"Speed vs. Accuracy: Shifting Attention Test (SAT)\nPopulation Spearman R={corr:.2f}, p={p:.6f}, N={len(population_df)}")
            plt.xlabel(f"Reaction Time\n{rt_interp}")
            plt.ylabel(f"Errors\n{err_interp}")
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            # Add quadrant labels to help interpretation
            plt.annotate("Fast & Accurate", xy=(x_min, population_df['err_score'].min()), 
                        xytext=(10, 10), textcoords='offset points', color='green')
            plt.annotate("Slow & Inaccurate", xy=(x_max, population_df['err_score'].max()), 
                        xytext=(-10, -10), textcoords='offset points', color='red', ha='right')
            
            plt.tight_layout()
            
            # Instead of saving to file, save to BytesIO
            img_data = BytesIO()
            plt.savefig(img_data, format='png', bbox_inches='tight', pad_inches=0.5)
            img_data.seek(0)
            plt.close()
            
            return img_data
        except Exception as e:
            print(f"Error creating plot: {e}")
            plt.close()
            return None
    
    except Exception as e:
        print(f"Error creating SAT speed-accuracy chart: {e}")
        return None


def create_domain_explanation_page(styles=None):
    """Generates the ReportLab flowables for the domain score explanation page using a table."""
    # If styles not provided, get them from the global function
    if styles is None:
        styles = get_styles()
        
    explanation_elements = []
    explanation_elements.append(Paragraph("<b>Cognitive Domain Explanations</b>", styles["Heading2"]))
    explanation_elements.append(Spacer(1, 10))
    explanation_elements.append(Paragraph("The cognitive assessment measures performance across multiple domains. Each domain score is derived from specific test components as described below:", styles["NormalSmall"]))
    explanation_elements.append(Spacer(1, 10))
    
    # Table header
    table_data = [
        [Paragraph("<b>Cognitive Domain</b>", styles["NormalSmall"]), Paragraph("<b>Calculation Method</b>", styles["NormalSmall"])],
    ]
    
    # Table data - updated to match the new domain order
    table_data.extend([
        [Paragraph("Executive Function", styles['NormalSmall']), Paragraph("SAT Correct Responses - SAT Errors", styles['NormalSmall'])],
        [Paragraph("Complex Attention", styles['NormalSmall']), Paragraph("Stroop Correct Responses - Stroop Commission Errors", styles['NormalSmall'])],
        [Paragraph("Simple Attention", styles['NormalSmall']), Paragraph("CPT Correct Responses - CPT Commission Errors", styles['NormalSmall'])],
        [Paragraph("Sustained Attention", styles['NormalSmall']), Paragraph("Sum(4PCPT P2-P4 Correct) - Sum(4PCPT P2-P4 Incorrect)", styles['NormalSmall'])],
        [Paragraph("Processing Speed", styles['NormalSmall']), Paragraph("SDC Correct Responses - SDC Errors", styles['NormalSmall'])],
        [Paragraph("Reaction Time", styles['NormalSmall']), Paragraph("Stroop RT + CPT RT + SAT RT (weighted average)", styles['NormalSmall'])],
        [Paragraph("Psychomotor Speed", styles['NormalSmall']), Paragraph("FTT Right Taps Average + FTT Left Taps Average + SDC Correct", styles['NormalSmall'])],
        [Paragraph("Motor Speed", styles['NormalSmall']), Paragraph("FTT Right Taps Average + FTT Left Taps Average", styles['NormalSmall'])],
        [Paragraph("Visual Memory", styles['NormalSmall']), Paragraph("BVMT-R Total Recall + BVMT-R Delayed Recall", styles['NormalSmall'])],
        [Paragraph("Verbal Memory", styles['NormalSmall']), Paragraph("VBM Total Recall + VBM Delayed Recall", styles['NormalSmall'])],
        [Paragraph("Working Memory", styles['NormalSmall']), Paragraph("4PCPT Part 4 Correct - Part 4 Incorrect", styles['NormalSmall'])],
        [Paragraph("Reasoning", styles['NormalSmall']), Paragraph("NVRT Correct Responses - NVRT Commission Errors", styles['NormalSmall'])],
        [Paragraph("Cognitive Flexibility", styles['NormalSmall']), Paragraph("SAT Correct Responses - SAT Errors + Stroop Interference Score", styles['NormalSmall'])],
    ])

    # Create the table
    # Adjust colWidths as needed, None allows auto-sizing
    col_widths = [130, None] 
    explanation_table = Table(table_data, colWidths=col_widths)

    # Style the table
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),      # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),              # Left align all
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),            # Middle align vertically
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font bold
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),           # Header padding
        ('TOPPADDING', (0, 0), (-1, -1), 5),              # Padding for all cells
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),          # Padding for all cells
        ('LEFTPADDING', (0, 0), (-1, -1), 8),             # Padding for all cells
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),            # Padding for all cells
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),     # Grid lines
        # Zebra striping (alternating background colors for rows)
        # Apply to rows starting from index 1 (skip header)
    ])
    # Apply zebra striping
    for i in range(1, len(table_data)):
        if i % 2 == 0: # Even rows (adjust index if header is included differently)
            style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)
        else: # Odd rows
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightblue)
            
    explanation_table.setStyle(style)

    explanation_elements.append(explanation_table)
    explanation_elements.append(Spacer(1, 12))
    
    explanation_elements.append(Paragraph("Note: Percentiles compare an individual's score to a normative group. A percentile of 50 represents average performance. Scores marked (INVALID) indicate the source test failed validity checks.", styles['ItalicSmall']))

    return explanation_elements


# --- Footer Function ---
def footer(canvas, doc, patient_info):
    """Draws the footer on each page with patient demographics."""
    # Ensure patient_info has enough elements to avoid IndexError
    pid = patient_info[0] if len(patient_info) > 0 else 'N/A'
    test_date = patient_info[1] if len(patient_info) > 1 else 'N/A'
    age = patient_info[2] if len(patient_info) > 2 else 'N/A'
    language = patient_info[3] if len(patient_info) > 3 else 'N/A'
    
    footer_text = f"Patient ID: {pid} | Age: {age} | Language: {language} | Test Date: {test_date}"
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(105 * mm, 10 * mm, footer_text) # Center based on A4 width approx 210mm
    canvas.restoreState()
# --- End Footer Function ---

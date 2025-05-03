import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, BaseDocTemplate, PageTemplate, Frame
from io import BytesIO
from .asrs_dsm_mapper import is_met, DSM5_ASRS_MAPPING
from reportlab.lib.units import mm, inch
import sqlite3
import pandas as pd
import os
from scipy import stats
import seaborn as sns
from collections import defaultdict
import logging
import json
from config_utils import get_lucid_data_db

# --- JSON-based Report Generation ---
import json
import os
from json_data_extractor import extract_patient_json

def generate_report_json(patient_id, output_path, json_dir="json", config=None):
    """
    Generate a report from patient data in JSON format.
    If the JSON does not exist, extract and save it first.
    Allows for flexible template/section selection via config dict.
    Args:
        patient_id (str): Patient identifier
        output_path (str): Output PDF path
        json_dir (str): Directory to store JSON files
        config (dict): Section toggles, e.g. {"include_npq": True, ...}
    """
    # Section toggles (override with config if provided)
    section_flags = {
        "include_demographics": True,
        "include_cognitive_scores": True,
        "include_subtests": True,
        "include_asrs": True,
        "include_dass": True,
        "include_epworth": True,
        "include_npq": True,
        # Add more flags as needed
    }
    if config:
        section_flags.update(config)
    # Ensure json_dir exists
    os.makedirs(json_dir, exist_ok=True)
    json_path = os.path.join(json_dir, f"{patient_id}.json")
    # Load or extract JSON
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = extract_patient_json(patient_id)
        if not data:
            raise ValueError(f"No data found for patient {patient_id}")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    # Optionally filter sections based on flags
    filtered_data = {}
    if section_flags["include_demographics"]:
        filtered_data["patient"] = data.get("patient", {})
    if section_flags["include_cognitive_scores"]:
        filtered_data["cognitive_scores"] = data.get("cognitive_scores", [])
    if section_flags["include_subtests"]:
        filtered_data["subtests"] = data.get("subtests", [])
    if section_flags["include_asrs"]:
        filtered_data["asrs"] = data.get("asrs", [])
    if section_flags["include_dass"]:
        filtered_data["dass_summary"] = data.get("dass_summary", [])
        filtered_data["dass_items"] = data.get("dass_items", [])
    if section_flags["include_epworth"]:
        filtered_data["epworth"] = data.get("epworth", {})
    if section_flags["include_npq"]:
        filtered_data["npq_scores"] = data.get("npq_scores", [])
        filtered_data["npq_questions"] = data.get("npq_questions", [])
    # Call the main report creation logic (e.g., create_fancy_report)
    create_fancy_report_json(filtered_data, output_path)
    return output_path

# Set up logging
logging.basicConfig(
    filename='report_generation.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # Overwrite existing log file
)

print("DEBUG: Using database at", os.path.abspath(get_lucid_data_db()))

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

def get_patient_test_scores(patient_id, test_config, db_path=None):
    if db_path is None:
        db_path = get_lucid_data_db()
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

def sanitize_table_data(table_data):
    def sanitize_cell(cell):
        if isinstance(cell, dict):
            return json.dumps(cell, indent=2)
        elif isinstance(cell, list):
            return ", ".join(str(sanitize_cell(x)) for x in cell)
        elif hasattr(cell, 'wrapOn'):
            return cell
        else:
            return str(cell)
    return [
        [sanitize_cell(cell) for cell in row]
        for row in table_data
    ]

def create_npq_section(data):
    from collections import defaultdict
    elements = []
    styles = get_styles()

    npq_scores = data.get("npq_scores", [])
    npq_questions = data.get("npq_questions", [])

    if not npq_scores:
        return []

    def severity_color(severity):
        s = severity.lower() if isinstance(severity, str) else str(severity)
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
                # row = (id, session_id, patient_id, domain, score, severity)
                if isinstance(row[3], str) and row[3].lower() == domain.lower():
                    score = row[4]
                    severity = row[5]
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

    # --- DEBUG: Print sample NPQ question row to confirm structure ---
    if npq_questions:
        print("[DEBUG] Sample npq_questions row:", npq_questions[0])

    # --- Use correct index for domain in npq_questions ---
    # Inspect the sample row and set the correct index here:
    # For now, try index 3 (change if debug output shows otherwise)
    DOMAIN_INDEX = 3

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
    table = Table(sanitize_table_data(full_table), colWidths=[250, 100, 150])
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
            domain = q[DOMAIN_INDEX]
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
            sev_key = severity.lower() if isinstance(severity, str) else str(severity)
            curr_key = current_severity.lower() if isinstance(current_severity, str) else str(current_severity)
            if severity_rank.get(sev_key, 0) > severity_rank.get(curr_key, 0):
                domain_severities[domain] = sev_key
        
        # Sort domains alphabetically for consistent presentation
        domains = sorted(grouped.keys())
        
        print(f"[DEBUG] Domains available in grouped: {list(grouped.keys())}")
        # Create table with headers
        response_rows = [("Question", "Score", "Severity")]
        
        # Add each domain and its questions
        for domain in domains:
            # Add domain header
            response_rows.append((domain, '', ''))
            
            # Sort questions by severity (severe to mild)
            questions = sorted(grouped[domain], key=lambda x: {
                'severe': 0, 'moderate': 1, 'mild': 2, 'none': 3
            }.get(x[2].lower() if isinstance(x[2], str) else str(x[2]), 3))
            
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
    import os
    # Path: root/images/LogoWB.png relative to this file
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'images', 'LogoWB.png'))
    logo_width = 20 * mm
    logo_height = 20 * mm
    x = doc.pagesize[0] - logo_width - 10
    y = doc.pagesize[1] - logo_height - 10
    if not os.path.exists(logo_path):
        print(f"[WARN] Logo not found at: {logo_path}")
        return
    try:
        canvas.drawImage(logo_path, x, y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')
    except Exception as e:
        print(f"[WARN] Could not draw logo: {e}")


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


def safe_append(elements, item, styles):
    """
    Append only valid ReportLab flowables to elements. If dict/list, convert to Paragraph.
    """
    from reportlab.platypus import Flowable
    if hasattr(item, 'wrapOn'):
        elements.append(item)
    elif isinstance(item, dict):
        elements.append(Paragraph(json.dumps(item, indent=2), styles['NormalSmall']))
    elif isinstance(item, list):
        for subitem in item:
            safe_append(elements, subitem, styles)
    else:
        elements.append(Paragraph(str(item), styles['NormalSmall']))

def create_fancy_report_json(data, output_path):
    """
    Writes the provided data dictionary to a JSON file at the specified output path.
    Ensures the output directory exists.
    """
    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created directory: {output_dir}")

        # Write the data to the JSON file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logging.info(f"Successfully wrote JSON report to {output_path}")

    except Exception as e:
        logging.error(f"Failed to write JSON report to {output_path}: {e}")
        raise # Re-raise the exception to signal failure

# -- Utility functions --
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate cognitive/ADHD report PDF.")
    parser.add_argument('--patient-id', type=str, required=True, help='Patient ID to generate report for')
    parser.add_argument('--output', type=str, required=True, help='Output PDF path')
    args = parser.parse_args()

    # Import fetch_all_patient_data from generate_report.py
    from generate_report.generate_report import fetch_all_patient_data
    data = fetch_all_patient_data(args.patient_id, get_lucid_data_db())
    if not data["patient"]:
        print(f"[ERROR] No patient data found for ID {args.patient_id}.")
        exit(1)
    create_fancy_report_json(data, args.output)
    print(f"[INFO] Report generated at {args.output}")

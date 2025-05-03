## **Structured Description of Cognitive Assessment Report (PDF)**

This document outlines the structure and content of the provided Cognitive Profile and ADHD Assessment report (Patient ID: 40436). Each section represents a distinct component of the report, suitable for modular development.

### **1\. Header & Footer Module**

* **Purpose:** Displays consistent branding and patient identification on each page.  
* **Content (Header \- variable):**  
  * Lucid Logo (Top Left/Right \- placement varies slightly, often top left on later pages).  
  * Report Title (Page 1 only): "Cognitive Profile and ADHD Assessment for Adults"  
* **Content (Footer \- consistent):**  
  * Patient ID  
  * Age  
  * Language  
  * Test Date  
  * Lucid Logo (Sometimes included in the footer text line, e.g., Pages 2, 3, 4, 8-19)  
* **Layout:** Typically a single line at the bottom of the page. Header elements vary per page.

### **2\. Demographics Module (Page 1\)**

* **Purpose:** Presents basic patient information.  
* **Content:**  
  * Patient ID: 40436  
  * Age: 50  
  * Language: English (United States)  
  * Test Date: April 11, 2025 17:37:55  
* **Layout:** Simple key-value pairs, positioned below the main title.

### **3\. Cognitive Domain Profile Module (Page 1\)**

* **Purpose:** Provides a visual overview of the patient's cognitive performance across various domains using percentiles.  
* **Content:**  
  * **Radar Chart:**  
    * Center: Overlapping colored shapes representing performance levels. Specific ADHD-related difficulties (Distractibility, Difficulty Sustaining Attention, Difficulty Waiting Turn, Fidgeting) are highlighted with labels and corresponding ASRS/DSM codes (e.g., 1h/A8).  
    * Axes: Radiate outwards, representing cognitive domains (Reasoning, Working Memory, Verbal Memory, Visual Memory, Motor Speed, Psychomotor Speed, Reaction Time, Processing Speed, Sustained Attention, Simple Attention, Complex Attention, Executive Function, Cognitive Flexibility).  
    * Data Points: Marked on each axis with the percentile score (e.g., Working Memory: 92, Simple Attention: 6).  
    * Background Shading: Circular bands indicating performance classifications (likely corresponding to the legend).  
  * **Legend:** Color-coded key defining percentile ranges and classifications:  
    * Very low (≤ 2%)  
    * Low (2-9%)  
    * Low average (9-25%)  
    * Average (25-75%)  
    * Above average (\> 75%)  
    * (Implicitly) Valid Score indicator (though not explicitly colored in the legend itself).  
* **Layout:** Large circular chart dominating the main section of the page, with the legend below it.

### **4\. Cognitive Domain Scores Table Module (Page 2\)**

* **Purpose:** Presents the numerical scores for each cognitive domain in a tabular format.  
* **Content:**  
  * Table Columns: Domain, Standard Score, Percentile, Classification, Valid (Yes/No).  
  * Table Rows: Each row represents a cognitive domain (Neurocognition Index (NCI), Composite Memory, Verbal Memory, Visual Memory, Psychomotor Speed, Reaction Time, Complex Attention, Cognitive Flexibility, Processing Speed, Executive Function, Reasoning, Working Memory, Sustained Attention, Simple Attention, Motor Speed).  
  * Data: Populated with the patient's specific scores and derived classifications. Asterisks (\*) likely indicate specific notes or considerations for certain scores (though the notes themselves aren't on this page).  
* **Layout:** Standard data table.

### **5\. Score Interpretation Table Module (Page 2\)**

* **Purpose:** Explains the meaning of the percentile classifications used in the report.  
* **Content:**  
  * Table Columns: Percentile Range, Classification, Clinical Interpretation.  
  * Table Rows: Defines each classification level (Above Average, Average, Low Average, Low, Very Low) based on percentile ranges and provides a brief clinical meaning (e.g., "Strengths", "Normal functioning", "Severe impairment").  
* **Layout:** Simple 3-column table.

### **6\. Subtest Results Table Module (Pages 2-4)**

* **Purpose:** Provides detailed scores for each individual cognitive test administered.  
* **Content:**  
  * Structure: A single logical table spanning multiple pages. Grouped by test name.  
  * Tests Covered: Verbal Memory Test (VBM), Visual Memory Test (VSM), Finger Tapping Test (FTT), Symbol Digit Coding Test (SDC), Stroop Test (ST), Shifting Attention Test (SAT), Continuous Performance Test (CPT), Reasoning Test (RT), Four Part Continuous Performance Test (FPCPT).  
  * Metrics per Test: Varies by test, but generally includes:  
    * Specific metrics (e.g., Correct Hits \- Immediate, Right Taps Average, Errors, Reaction Time).  
    * Raw Score (sometimes labeled just "Score").  
    * Standard Score (derived score).  
    * Percentile.  
  * Data: Patient's specific scores for each metric. Asterisks (\*) indicate specific metrics, possibly those related to speed or errors.  
* **Layout:** Multi-page table with clear headings for each subtest.

### **7\. Speed vs. Accuracy Analysis Module (Page 5\)**

* **Purpose:** Visualizes the patient's trade-off between response speed and accuracy compared to a population sample for specific tests.  
* **Content:**  
  * **Introduction Text:** Explains the charts' purpose.  
  * **Scatter Plots (x3):**  
    * Tests: Shifting Attention Test (SAT), Stroop Test, Reasoning Test.  
    * Axes: X-axis \= Reaction Time (Lower \= Faster), Y-axis \= Errors (Higher \= Worse).  
    * Data Points:  
      * Population data (grey dots).  
      * Population trend line (red line, with Spearman R, p-value, N).  
      * Population Median Speed/Error (dashed lines).  
      * Norm Median Speed/Error (dashed lines).  
      * Patient's performance (single large blue dot, labeled "Patient").  
  * **Interpretation Text:** Explains the general speed-accuracy trends observed in the population data for each test shown.  
* **Layout:** Three distinct chart areas, each with a title, plot, and legend. Explanatory text above and below the charts.

### **8\. ASRS to DSM-5 Mapping Module (Page 6\)**

* **Purpose:** Maps the patient's responses on the Adult ADHD Self-Report Scale (ASRS) to the DSM-5 diagnostic criteria for ADHD.  
* **Content:**  
  * **Criterion A (Inattention):**  
    * Table mapping DSM-5 criteria (A1-A9) descriptions to specific ASRS questions (Q1-Q4, Q7-Q11).  
    * Columns: Criterion Description, ASRS Question Text, Patient's Response (e.g., "Often", "Very Often", "Sometimes"), Met (Yes/No).  
    * Summary Row: Total criteria met (e.g., 9/9), Requirement (Need ≥5), Overall Met (Yes/No).  
  * **Criterion B (Hyperactivity/Impulsivity):**  
    * Similar table structure mapping B1-B9 to ASRS questions (Q5, Q6, Q12-Q18).  
    * Summary Row: Total criteria met (e.g., 6/9), Requirement (Need ≥5), Overall Met (Yes/No).  
  * **ADHD Diagnosis Summary:**  
    * Simple list indicating if Inattention and Hyperactivity/Impulsivity criteria were met.  
    * Overall Diagnosis based on met criteria (e.g., "Combined Presentation").  
* **Layout:** Two main tables followed by a short summary section.

### **9\. NPQ LF-207 Diagnostic Screen Summary Module (Page 7\)**

* **Purpose:** Presents a summary of potential symptom burden across various domains based on the Neuropsychiatric Questionnaire (NPQ). Emphasizes it's a screening tool, not diagnostic.  
* **Content:**  
  * **Disclaimer Text:** Explains the tool's purpose and limitations.  
  * **Symptom Summary Table:**  
    * Grouped by category (Attention & Hyperactivity, Anxiety, Mood, Autism Spectrum, Other Concerns).  
    * Rows: Specific scales/symptom areas (e.g., ADHD, Anxiety, Depression, Panic, Autism, Somatic, Pain, MCI).  
    * Columns: Symptom Area, Score (numerical), Severity (Categorical: e.g., Mild, Not a problem).  
  * **Severity Color Legend:** Defines colors used (implicitly in an interactive version, explicitly listed here) for Severe, Moderate, Mild, None.  
* **Layout:** Text disclaimer followed by a structured table, and a legend.

### **10\. Detailed NPQ Responses Module (Pages 8-18)**

* **Purpose:** Provides the patient's specific response to each individual question on the NPQ LF-207.  
* **Content:**  
  * **Multi-page Table:**  
    * Grouped by the same scales/symptom areas as the NPQ summary (Page 7).  
    * Columns: Question Text, Score (0-3, representing frequency/severity), Severity (Categorical text: Not a problem, A mild problem, A moderate problem, A severe problem).  
    * Data: Lists every question within each scale and the patient's corresponding response score and severity level.  
* **Layout:** A long, continuous table spanning multiple pages, organized by symptom category headings.

### **11\. Cognitive Domain Explanations Module (Page 19\)**

* **Purpose:** Explains how the main cognitive domain scores (from Page 2\) were calculated from the subtest results (Pages 2-4).  
* **Content:**  
  * **Introduction Text:** Briefly explains the table's purpose.  
  * **Calculation Table:**  
    * Columns: Cognitive Domain, Calculation Method.  
    * Rows: Lists each main cognitive domain (Executive Function, Complex Attention, etc.).  
    * Calculation Method: Describes the formula using subtest names and metrics (e.g., "SAT Correct Responses \- SAT Errors", "Stroop RT \+ CPT RT \+ SAT RT (weighted average)"). Abbreviations (SAT, CPT, SDC, FTT, VBM, BVMT-R, NVRT, 4PCPT) are used.  
  * **Note:** Clarifies percentile meaning and the significance of (INVALID) scores (though none appear invalid in this specific report).  
* **Layout:** Short introductory text followed by a two-column table.
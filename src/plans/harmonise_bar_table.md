# Harmonising Subtest Results Table and Visual Indicators

## Summary of Achievements

### 1. Centered Subtest Table Headings
- The column headings for the Subtest Results table ("Metric", "Score", "Standard Score", "Percentile") are now centered using the `text-center` class.
- This improves readability and visual alignment, making the table more professional and easier to scan.

### 2. Clearer Heading Labels
- The heading "Standard" has been updated to "Standard Score" for clarity and consistency with clinical terminology.

### 3. Visual Invalid Badge
- For any subtest metric where `validity_index` is not "yes", a visible red `Invalid` badge appears next to the metric name in the table.
- This uses the `.badge-invalid` CSS class for consistent styling and immediate visual feedback.

### 4. Robust, Modular Implementation
- All changes are implemented in a modular, non-repetitive way within the JavaScript `populateReport()` function.
- Only the Subtest Results table logic is affected, ensuring orthogonality and maintainability.
- No other tables or unrelated report sections are changed.

## How It Works

- The report template uses dynamic JavaScript to populate tables from a JSON data source.
- When rendering the Subtest Results section:
  - The code checks each metric's `validity_index`.
  - If a metric is invalid, the badge is appended to the metric name.
  - Table headings are always centered for clarity.
- These changes ensure that clinicians and users can quickly spot invalid results and interpret scores with maximum clarity.

## Benefits
- **Clarity:** Visual cues and alignment make the report easier to interpret.
- **Consistency:** Adheres to clinical and user interface best practices.
- **Maintainability:** Changes are modular and easy to extend or modify.

---

*This document summarises the harmonisation of the Subtest Results table and the addition of visual indicators for invalid results in the ADHD Cognitive Assessment Report template.*

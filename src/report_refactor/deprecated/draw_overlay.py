import sys
from cognitive_importer import draw_asrs_debug_overlay  # make sure it's defined there

# Call the function with your inputs
draw_asrs_debug_overlay(
    pdf_path="34766-fixed.pdf",
    bounding_box_csv="bounding_boxes.csv"
)

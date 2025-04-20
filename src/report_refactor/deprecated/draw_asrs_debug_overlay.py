import fitz  # PyMuPDF
import csv
import os

def draw_asrs_debug_overlay(pdf_path, bounding_box_csv, output_path="asrs_debug_overlay.pdf"):
    doc = fitz.open(pdf_path)

    # Load bounding boxes from CSV
    with open(bounding_box_csv, newline='') as f:
        reader = csv.DictReader(f)
        boxes = [row for row in reader]

    for page_num, page in enumerate(doc):
        # Only visualize page 4 (0-indexed as 3)
        if page_num != 3:
            continue

        for box in boxes:
            x0 = float(box["x0"])
            y0 = float(box["y0"])
            x1 = float(box["x1"])
            y1 = float(box["y1"])
            label = f'{box["Part"]}{box["Question"]}: {box["Response"]}'

            rect = fitz.Rect(x0, y0, x1, y1)
            page.draw_rect(rect, color=(0, 0, 1), width=0.5)  # Blue box
            page.insert_text((x0, y0 - 5), label, fontsize=4, color=(0, 0, 1))

        # Highlight all X-like marks
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip() in ["X", "×", "■", "☒", "✘"]:
                        rect = fitz.Rect(*span["bbox"])
                        page.draw_rect(rect, color=(1, 0, 0), width=1)  # Red box
                        page.insert_text((rect.x0, rect.y1 + 2), span["text"], fontsize=6, color=(1, 0, 0))

    doc.save(output_path)
    print(f"[DEBUG] Saved overlay PDF to: {output_path}")

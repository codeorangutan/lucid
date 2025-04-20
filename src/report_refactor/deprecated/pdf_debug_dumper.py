import fitz  # PyMuPDF
import os

DB_PATH = "cognitive_analysis.db"
PDF_PATH = "40277.pdf"

def dump_pdf_pages(pdf_path, output_folder="debug_pages"):
    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)

    for i, page in enumerate(doc):
        lines = []
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # top-down, left-right

        for b in blocks:
            for line in b[4].splitlines():
                line = line.strip()
                if line:
                    lines.append(line)

        debug_file = os.path.join(output_folder, f"debug_page_{i}.txt")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"[DEBUG] Dumped page {i} → {debug_file}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python pdf_debug_dumper.py path/to/file.pdf")
    else:
        dump_pdf_pages(sys.argv[1])

import fitz  # PyMuPDF
import os
import concurrent.futures

def dump_page(doc, i, output_folder):
    try:
        page = doc[i]
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # top-down, left-right

        lines = []
        for b in blocks:
            for line in b[4].splitlines():
                line = line.strip()
                if line:
                    lines.append(line)

        debug_file = os.path.join(output_folder, f"debug_page_{i}.txt")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"[DEBUG] Dumped page {i+1}/{len(doc)} → {debug_file}")
    except Exception as e:
        print(f"[ERROR] Failed on page {i+1}: {e}")

def dump_pdf_pages(pdf_path, output_folder="debug_pages", parallel=False):
    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"[INFO] Found {total_pages} pages in {pdf_path}")

    if parallel:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(dump_page, doc, i, output_folder) for i in range(total_pages)]
            concurrent.futures.wait(futures)
    else:
        for i in range(total_pages):
            dump_page(doc, i, output_folder)

    print(f"[INFO] Finished dumping all {total_pages} pages")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_debug_dumper.py path/to/file.pdf [--parallel]")
    else:
        pdf_path = sys.argv[1]
        use_parallel = "--parallel" in sys.argv
        dump_pdf_pages(pdf_path, parallel=use_parallel)

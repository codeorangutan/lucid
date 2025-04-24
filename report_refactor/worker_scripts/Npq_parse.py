import pdfplumber

pdf_path = "40277.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    for i in range(len(pdf.pages)):
        try:
            page = pdf.pages[i]
            words = page.extract_words()
            print(f"Page {i+1}: {len(words)} words")
        except Exception as e:
            print(f"Page {i+1} failed: {e}")

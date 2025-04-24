import pdfplumber

pdf_path = "40277.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    
    for i in range(5, 13):  # Pages 6 to 13 (0-indexed)
        try:
            print(f"\n--- Page {i+1} ---")
            page = pdf.pages[i]
            text = page.extract_text()
            print(f"Text length: {len(text) if text else 0}")
            words = page.extract_words()
            print(f"Words found: {len(words)}")
            if words:
                print("First few words:", [w["text"] for w in words[:10]])
        except Exception as e:
            print(f"Page {i+1} failed: {e}")

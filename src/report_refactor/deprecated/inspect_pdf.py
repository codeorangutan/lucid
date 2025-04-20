import fitz  # PyMuPDF

def inspect_pdf_page(pdf_path, page_number):
    """
    Extract and print text from a specific page in a PDF to inspect its format.
    
    Args:
        pdf_path (str): Path to the PDF file
        page_number (int): 1-based page number to inspect
    """
    try:
        # Open the PDF
        doc = fitz.open(pdf_path)
        
        # Adjust for 0-based indexing
        page_idx = page_number - 1
        
        if page_idx < 0 or page_idx >= len(doc):
            print(f"Error: Page {page_number} is out of range. PDF has {len(doc)} pages.")
            doc.close()
            return
        
        # Get the page
        page = doc[page_idx]
        
        # Extract text blocks
        print(f"\n===== TEXT BLOCKS FROM PAGE {page_number} =====")
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (b[1], b[0]))  # Sort top-down, left-right
        
        for i, block in enumerate(blocks):
            if len(block) >= 7 and block[6] == 0:  # It's a text block
                print(f"\n--- BLOCK {i+1} ---")
                print(block[4])  # Print the text content
        
        # Extract raw text
        print(f"\n===== RAW TEXT FROM PAGE {page_number} =====")
        text = page.get_text()
        print(text)
        
        doc.close()
        
    except Exception as e:
        print(f"Error inspecting PDF: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python inspect_pdf.py <pdf_file> <page_number>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page_number = int(sys.argv[2])
    
    inspect_pdf_page(pdf_path, page_number)

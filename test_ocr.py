"""
Debug script to test OCR extraction on ART - 17031.pdf
"""

import zipfile
from pathlib import Path

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

ZIP_PATH = "/workspaces/pdfproject/2025 (1).zip"
INNER_FOLDER = "2025"

def extract_text_from_images_ocr(pdf_bytes: bytes, filename: str) -> str:
    """Extract text from images in PDF using Tesseract OCR."""
    if not HAS_OCR:
        print("OCR not available")
        return ""
    
    try:
        # Convert PDF to images (first 3 pages)
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=3)
        print(f"Extracted {len(images)} page(s) as images")
        ocr_texts = []
        
        for page_num, image in enumerate(images, 1):
            try:
                text = pytesseract.image_to_string(image)
                print(f"\n--- PAGE {page_num} OCR TEXT ({len(text)} chars) ---")
                print(text[:500])  # Print first 500 chars
                if text.strip():
                    ocr_texts.append(text)
            except Exception as e:
                print(f"[OCR page {page_num}] Error: {e}")
        
        combined = "\n".join(ocr_texts)
        print(f"\n--- COMBINED OCR TEXT ({len(combined)} chars) ---")
        return combined
    except Exception as e:
        print(f"[Image extraction error] {e}")
        return ""

def main():
    target_file = "ART - 17031.pdf"
    
    zip_path = Path(ZIP_PATH)
    prefix = INNER_FOLDER.rstrip("/") + "/"
    target_entry = prefix + target_file

    print("Testing OCR extraction on ART - 17031.pdf\n")
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open(target_entry) as fh:
            file_bytes = fh.read()
        
        ocr_text = extract_text_from_images_ocr(file_bytes, target_file)
        
        # Check for keywords
        print(f"\nSearching for keywords...")
        print(f"'galderma' in OCR: {'galderma' in ocr_text.lower()}")
        print(f"'international' in OCR: {'international' in ocr_text.lower()}")

if __name__ == "__main__":
    main()

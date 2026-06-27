"""
Test single file: ART - 15230.pdf
"""

import re
import zipfile
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

ENDPOINT = "https://extract-pdf-anlysis.cognitiveservices.azure.com/"
KEY = "b1b266e81809453aafa2421913b7b793"
SEARCH_TEXT = "Galderma int"
FALLBACK_MATCH_WORDS = ("galderma", "international")
ZIP_PATH = "/workspaces/pdfproject/2025 (1).zip"
INNER_FOLDER = "2025"
MODEL_ID = "prebuilt-read"

def build_client():
    return DocumentIntelligenceClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(KEY)
    )

def _noisy_word_pattern(word: str) -> str:
    return r"\W*".join(re.escape(ch) for ch in word.lower())

def extract_text_from_images_ocr(pdf_bytes: bytes, filename: str) -> str:
    if not HAS_OCR:
        return ""
    try:
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=5)
        ocr_texts = []
        for page_num, image in enumerate(images, 1):
            try:
                text = pytesseract.image_to_string(image)
                if text.strip():
                    ocr_texts.append(text)
            except:
                continue
        return "\n".join(ocr_texts)
    except:
        return ""

target_file = "ART - 15230.pdf"
zip_path = Path(ZIP_PATH)
prefix = INNER_FOLDER.rstrip("/") + "/"
target_entry = prefix + target_file

print(f"Testing: {target_file}\n")

client = build_client()

with zipfile.ZipFile(zip_path, "r") as zf:
    with zf.open(target_entry) as fh:
        file_bytes = fh.read()

    # Get Azure extracted text
    poller = client.begin_analyze_document(MODEL_ID, body=file_bytes, content_type="application/octet-stream")
    result = poller.result()
    azure_text = result.content or ""

    # Get OCR extracted text
    ocr_text = extract_text_from_images_ocr(file_bytes, target_file)

    print(f"Azure extracted {len(azure_text)} characters")
    print(f"OCR extracted {len(ocr_text)} characters")
    
    combined = azure_text + "\n" + ocr_text
    lowered = combined.lower()
    
    print(f"\nSearching in combined text:")
    print(f"  'galderma': {('galderma' in lowered)}")
    print(f"  'international': {('international' in lowered)}")
    
    # Show snippets
    if 'galderma' in lowered:
        idx = lowered.find('galderma')
        print(f"\nGalderma context: ...{combined[max(0,idx-20):idx+80]}...")
    
    if 'international' in lowered:
        idx = lowered.find('international')
        print(f"International context: ...{combined[max(0,idx-20):idx+100]}...")

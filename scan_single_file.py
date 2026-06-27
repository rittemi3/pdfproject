"""
Scan a single document using Azure Document Intelligence with OCR fallback.
"""

import argparse
import re
import zipfile
from pathlib import Path
from io import BytesIO

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from ocr_fallback import HAS_OCR, extract_text_from_images_ocr

# Configuration from scan_documents.py
ENDPOINT = "https://extract-pdf-anlysis.cognitiveservices.azure.com/"
KEY = "b1b266e81809453aafa2421913b7b793"
SEARCH_TEXT = "Galderma int"
ZIP_PATH = "/workspaces/pdfproject/2025 (1).zip"
INNER_FOLDER = "2025"
MODEL_ID = "prebuilt-read"

SUPPORTED_EXTENSIONS = {
    ".pdf", ".jpeg", ".jpg", ".png", ".bmp", ".tiff", ".tif",
    ".heif", ".docx", ".pptx", ".html", ".htm", ".ai"
}


def build_client() -> DocumentIntelligenceClient:
    return DocumentIntelligenceClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(KEY)
    )


def matches_target_text(extracted_text: str) -> bool:
    """Return True when SEARCH_TEXT terms appear in order, allowing separators."""
    # Match the search phrase even when OCR/API inserts line breaks or punctuation
    # between tokens (e.g. "Galderma\nInternational" or "Galderma - int...").
    # The final token is treated as a prefix so "int" matches "international".
    tokens = [re.escape(token) for token in SEARCH_TEXT.lower().split() if token]
    if not tokens:
        return False
    if len(tokens) == 1:
        pattern = r"\b" + tokens[0] + r"[a-z0-9]*"
    else:
        pattern = (
            r"\b"
            + r"[^a-z0-9]+".join(tokens[:-1])
            + r"[^a-z0-9]+"
            + tokens[-1]
            + r"[a-z0-9]*"
        )
    return re.search(pattern, extracted_text.lower()) is not None


def contains_search_text(client: DocumentIntelligenceClient, file_bytes: bytes, filename: str) -> bool:
    """
    Send file bytes to Azure Document Intelligence and check whether
    SEARCH_TEXT appears in the extracted content.
    
    Approach:
    1. First try standard text extraction with strict consecutive match.
    2. For PDF files only, try OCR and apply the same strict match.
    
    Returns True if found via either method.
    """
    try:
        poller = client.begin_analyze_document(
            MODEL_ID,
            body=file_bytes,
            content_type="application/octet-stream",
        )
        result = poller.result()
        full_text = result.content or ""
        
        # Check with standard text extraction
        if matches_target_text(full_text):
            return True

        if filename.lower().endswith('.pdf'):
            # Try OCR on images and apply the same strict consecutive match.
            ocr_text = extract_text_from_images_ocr(file_bytes, filename)
            if ocr_text and matches_target_text(full_text + "\n" + ocr_text):
                print("         *** MATCH FOUND: SEARCH_TEXT detected via image OCR ***")
                return True
            if not HAS_OCR:
                print("         OCR fallback unavailable (install pdf2image, pytesseract, Pillow)")
        
        return False
    except HttpResponseError as exc:
        print(f"  [API error] {filename}: {exc.message}")
        return False
    except Exception as exc:
        print(f"  [Error] {filename}: {exc}")
        return False


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def scan_single_file(client: DocumentIntelligenceClient, target_filename: str) -> bool:
    """Scan a single file from the zip archive."""
    zip_path = Path(ZIP_PATH)
    if not zip_path.exists():
        print(f"ERROR: Zip file not found at {ZIP_PATH}")
        return False

    prefix = INNER_FOLDER.rstrip("/") + "/"
    target_entry = prefix + target_filename

    print(f"Scanning: {target_filename}")
    print(f"Searching for: \"{SEARCH_TEXT}\"\n")

    with zipfile.ZipFile(zip_path, "r") as zf:
        try:
            with zf.open(target_entry) as fh:
                file_bytes = fh.read()
            if contains_search_text(client, file_bytes, target_filename):
                print(f"\n*** MATCH: '{SEARCH_TEXT}' found in {target_filename} ***")
                return True
            else:
                print(f"\n*** NO MATCH: '{SEARCH_TEXT}' not found in {target_filename} ***")
                return False
        except KeyError:
            print(f"ERROR: File '{target_entry}' not found in zip archive.")
            return False


def scan_local_file(client: DocumentIntelligenceClient, file_path: Path) -> bool:
    """Scan a single local file path."""
    if not file_path.exists() or not file_path.is_file():
        print(f"ERROR: File not found: {file_path}")
        return False

    if not is_supported(file_path.name):
        print(f"ERROR: Unsupported file type: {file_path.suffix}")
        return False

    print(f"Scanning local file: {file_path}")
    print(f"Searching for: \"{SEARCH_TEXT}\"\n")

    file_bytes = file_path.read_bytes()
    if contains_search_text(client, file_bytes, file_path.name):
        print(f"\n*** MATCH: '{SEARCH_TEXT}' found in {file_path.name} ***")
        return True

    print(f"\n*** NO MATCH: '{SEARCH_TEXT}' not found in {file_path.name} ***")
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan one document either from a local file path or a configured zip entry."
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        help="Optional local file path to scan directly (for example: '/path/to/file.pdf').",
    )
    return parser.parse_args()


def main() -> None:
    target_file = "ART - 17031.pdf"
    args = parse_args()
    
    print("Azure Document Intelligence — single file scanner")
    print("=" * 60)
    
    client = build_client()
    if args.file_path:
        scan_local_file(client, Path(args.file_path))
    else:
        scan_single_file(client, target_file)


if __name__ == "__main__":
    main()

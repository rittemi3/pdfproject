"""
Scan documents using Azure Document Intelligence with OCR fallback for graphics.
Reads files from a local path (zip archive or directory),
sends each to Azure Document Intelligence, and records filenames
where the text "Galderma int" is found.

When "Galderma" is found but "International" is not in extracted text,
falls back to OCR image extraction to find graphical text.

Requirements:
    pip install azure-ai-documentintelligence azure-core pdf2image pytesseract Pillow
    apt-get install tesseract-ocr

Usage:
    python scan_documents.py
"""

import os
import re
import zipfile
from pathlib import Path
from io import BytesIO

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from ocr_fallback import HAS_OCR, extract_text_from_images_ocr

# ---------------------------------------------------------------------------
# Configuration — edit these values before running
# ---------------------------------------------------------------------------

ENDPOINT = "https://extract-pdf-anlysis.cognitiveservices.azure.com/"

# Your Azure Document Intelligence key
KEY = "b1b266e81809453aafa2421913b7b793"

# Text to search for (case-insensitive)
SEARCH_TEXT = "Galderma int"

# Path to the zip file (upload it to this workspace folder)
ZIP_PATH      = "/workspaces/pdfproject/2024.zip"
INNER_FOLDER  = "2024"   # folder inside the zip

# Fallback: path to the extracted folder if you extracted the zip manually
EXTRACTED_DIR = "/workspaces/pdfproject/__pycache__/2025_part_2"

# Result file listing matched filenames, one per line
OUTPUT_FILE = "matching_files.txt"

# Azure Document Intelligence model to use (prebuilt-read extracts all text)
MODEL_ID = "prebuilt-read"

# File extensions that Document Intelligence can process
SUPPORTED_EXTENSIONS = {
    ".pdf", ".jpeg", ".jpg", ".png", ".bmp", ".tiff", ".tif",
    ".heif", ".docx", ".pptx", ".html", ".htm", ".ai"
}

# ---------------------------------------------------------------------------


def build_client() -> DocumentIntelligenceClient:
    return DocumentIntelligenceClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(KEY)
    )


def matches_target_text(extracted_text: str) -> bool:
    """Return True when SEARCH_TEXT terms appear in order, allowing separators."""
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
            # Keep OCR fallback behavior consistent with single-file scanning.
            ocr_text = extract_text_from_images_ocr(file_bytes, filename)
            if ocr_text and matches_target_text(full_text + "\n" + ocr_text):
                print(f"         *** MATCH: {filename} (via image OCR) ***")
                return True
            if not HAS_OCR:
                print("         OCR fallback unavailable (install pdf2image, pytesseract, Pillow)")
        
        return False
    except HttpResponseError as exc:
        print(f"  [API error] {filename}: {exc.message}")
        return False
    except Exception as exc:  # pylint: disable=broad-except
        print(f"  [Error] {filename}: {exc}")
        return False


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def scan_zip(client: DocumentIntelligenceClient) -> list[str]:
    """Read files from inside the zip archive and return matching filenames."""
    zip_path = Path(ZIP_PATH)
    if not zip_path.exists():
        return []

    matching: list[str] = []
    prefix = INNER_FOLDER.rstrip("/") + "/"

    with zipfile.ZipFile(zip_path, "r") as zf:
        entries = [
            e for e in zf.namelist()
            if e.startswith(prefix) and not e.endswith("/") and is_supported(e)
        ]

        total = len(entries)
        print(f"Found {total} supported file(s) inside '{zip_path.name}/{INNER_FOLDER}'.\n")

        for idx, entry in enumerate(entries, start=1):
            display_name = entry[len(prefix):]  # relative name inside folder
            print(f"[{idx:>{len(str(total))}}/{total}] {display_name}")
            with zf.open(entry) as fh:
                file_bytes = fh.read()
            if contains_search_text(client, file_bytes, display_name):
                print(f"         *** MATCH: {display_name} ***")
                matching.append(display_name)

    return matching


def scan_directory(client: DocumentIntelligenceClient, directory: Path) -> list[str]:
    """Read files from a local directory and return matching filenames."""
    all_files = sorted(
        f for f in directory.rglob("*") if f.is_file() and is_supported(f.name)
    )

    total = len(all_files)
    print(f"Found {total} supported file(s) in '{directory}'.\n")

    matching: list[str] = []
    for idx, filepath in enumerate(all_files, start=1):
        print(f"[{idx:>{len(str(total))}}/{total}] {filepath.name}")
        with open(filepath, "rb") as fh:
            file_bytes = fh.read()
        if contains_search_text(client, file_bytes, filepath.name):
            print(f"         *** MATCH: {filepath.name} ***")
            matching.append(filepath.name)

    return matching


def write_output(matching: list[str]) -> None:
    """Write only matching filenames to OUTPUT_FILE, one filename per line."""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        for name in matching:
            fh.write(name + "\n")
    print(f"\nResults saved to: {OUTPUT_FILE}")


def main() -> None:
    print("Azure Document Intelligence — document scanner")
    print(f"Searching for: \"{SEARCH_TEXT}\"\n")

    client = build_client()
    matching: list[str] = []

    # Priority 1: zip archive
    if Path(ZIP_PATH).exists():
        print(f"Source: zip archive at {ZIP_PATH}")
        matching = scan_zip(client)

    # Priority 2: extracted directory
    elif Path(EXTRACTED_DIR).is_dir():
        print(f"Source: directory at {EXTRACTED_DIR}")
        matching = scan_directory(client, Path(EXTRACTED_DIR))

    else:
        print(
            f"ERROR: Neither the zip file '{ZIP_PATH}' nor the extracted directory "
            f"'{EXTRACTED_DIR}' could be found. Please check the paths."
        )
        return

    print(f"\n{'='*60}")
    print(f"Scan complete. {len(matching)} matching file(s) found.")
    write_output(matching)


if __name__ == "__main__":
    main()

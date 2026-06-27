"""
Debug script to see what text Azure Document Intelligence actually extracts.
"""

import re
import zipfile
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

# Configuration
ENDPOINT = "https://extract-pdf-anlysis.cognitiveservices.azure.com/"
KEY = "b1b266e81809453aafa2421913b7b793"
SEARCH_TEXT = "Galderma int"
ZIP_PATH = "/workspaces/pdfproject/2025 (1).zip"
INNER_FOLDER = "2025"
MODEL_ID = "prebuilt-read"


def build_client() -> DocumentIntelligenceClient:
    return DocumentIntelligenceClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(KEY)
    )


def debug_extract_text(client: DocumentIntelligenceClient, target_filename: str) -> None:
    """Extract and display raw text from the PDF."""
    zip_path = Path(ZIP_PATH)
    if not zip_path.exists():
        print(f"ERROR: Zip file not found at {ZIP_PATH}")
        return

    prefix = INNER_FOLDER.rstrip("/") + "/"
    target_entry = prefix + target_filename

    print(f"Extracting text from: {target_filename}\n")
    print("=" * 60)

    with zipfile.ZipFile(zip_path, "r") as zf:
        try:
            with zf.open(target_entry) as fh:
                file_bytes = fh.read()
            
            try:
                poller = client.begin_analyze_document(
                    MODEL_ID,
                    body=file_bytes,
                    content_type="application/octet-stream",
                )
                result = poller.result()
                full_text = result.content or ""
                
                print(f"EXTRACTED TEXT ({len(full_text)} characters):\n")
                print(full_text)
                print("\n" + "=" * 60)
                print(f"\nSearching for: '{SEARCH_TEXT}'")
                print(f"Found: {SEARCH_TEXT.lower() in full_text.lower()}")
                
            except HttpResponseError as exc:
                print(f"[API error] {filename}: {exc.message}")
            except Exception as exc:
                print(f"[Error] {filename}: {exc}")
                
        except KeyError:
            print(f"ERROR: File '{target_entry}' not found in zip archive.")


def main() -> None:
    target_file = "ART - 17156.pdf"
    
    print("Azure Document Intelligence — TEXT EXTRACTION DEBUG")
    print("=" * 60 + "\n")
    
    client = build_client()
    debug_extract_text(client, target_file)


if __name__ == "__main__":
    main()

"""Shared OCR fallback utilities for PDF scanning scripts."""

import warnings

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


OCR_MAX_PAGES = 5
OCR_PRIMARY_DPI = 300
OCR_FALLBACK_DPI = 200
# Keep this below Pillow's default decompression-bomb warning threshold.
OCR_MAX_IMAGE_PIXELS = 80_000_000


def _render_pdf_page(pdf_bytes: bytes, page_num: int, dpi: int):
    """Render one PDF page and return a PIL Image, or None if page does not exist."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=page_num,
            last_page=page_num,
        )
    if not images:
        return None
    return images[0]


def extract_text_from_images_ocr(pdf_bytes: bytes, filename: str) -> str:
    """
    Extract text from images in PDF using Tesseract OCR.
    Called as fallback when standard extraction does not contain target text.

    Returns: concatenated OCR text from all images in the PDF.
    """
    if not HAS_OCR:
        return ""

    try:
        ocr_texts = []

        for page_num in range(1, OCR_MAX_PAGES + 1):
            text = ""
            page_exists = False
            last_error = None

            # Retry at lower DPI when high-resolution rendering is too large.
            for dpi in (OCR_PRIMARY_DPI, OCR_FALLBACK_DPI):
                image = None
                try:
                    image = _render_pdf_page(pdf_bytes, page_num, dpi)
                    if image is None:
                        break

                    page_exists = True
                    pixel_count = image.width * image.height
                    if pixel_count > OCR_MAX_IMAGE_PIXELS:
                        raise ValueError(
                            f"page image too large at {dpi} DPI "
                            f"({pixel_count} pixels)"
                        )

                    text = pytesseract.image_to_string(image)
                    break
                except Exception as e:
                    last_error = e
                    continue
                finally:
                    if image is not None:
                        image.close()

            if not page_exists:
                break

            if not text and last_error is not None:
                print(f"    [OCR page {page_num}] {filename}: {last_error}")

            if text.strip():
                ocr_texts.append(text)

        return "\n".join(ocr_texts)
    except Exception as e:
        print(f"    [Image extraction error] {filename}: {e}")
        return ""

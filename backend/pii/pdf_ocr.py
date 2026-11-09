
"""PDF text extraction and OCR with page-coordinate mapping."""

from __future__ import annotations

import io
import os
from typing import Any

import pymupdf
import pytesseract
from PIL import Image
from pytesseract import Output


# Explicit Windows path: does not depend on Windows PATH.
# Optional explicit Tesseract executable path.
# If not configured, pytesseract searches the system PATH.
TESSERACT_CMD = os.getenv("TESSERACT_CMD")

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

DEFAULT_OCR_LANGUAGE = "eng"
MIN_NATIVE_TEXT_LENGTH = 20
OCR_RENDER_SCALE = 2.0


def _native_page_words(
    page: pymupdf.Page,
) -> list[dict[str, Any]]:
    """Extract native PDF words and their bounding boxes."""
    words = []

    for item in page.get_text("words"):
        x0, y0, x1, y1, text = item[:5]

        text = str(text).strip()

        if not text:
            continue

        words.append(
            {
                "text": text,
                "bbox": [
                    float(x0),
                    float(y0),
                    float(x1),
                    float(y1),
                ],
                "confidence": 1.0,
            }
        )

    return words


def _ocr_page(
    page: pymupdf.Page,
    language: str = DEFAULT_OCR_LANGUAGE,
) -> dict[str, Any]:
    """OCR a page and map word boxes back to PDF coordinates."""

    matrix = pymupdf.Matrix(
        OCR_RENDER_SCALE,
        OCR_RENDER_SCALE,
    )

    pixmap = page.get_pixmap(
        matrix=matrix,
        colorspace=pymupdf.csRGB,
        alpha=False,
    )

    image = Image.frombytes(
        "RGB",
        (pixmap.width, pixmap.height),
        pixmap.samples,
    )

    data = pytesseract.image_to_data(
        image,
        lang=language,
        config="--psm 3",
        output_type=Output.DICT,
    )

    # Map rendered-image pixels back to PDF page coordinates.
    scale_x = page.rect.width / image.width
    scale_y = page.rect.height / image.height

    words = []
    text_parts = []

    for index, raw_text in enumerate(data["text"]):
        word = str(raw_text).strip()

        if not word:
            continue

        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1.0

        x = float(data["left"][index])
        y = float(data["top"][index])
        width = float(data["width"][index])
        height = float(data["height"][index])

        x0 = x * scale_x
        y0 = y * scale_y
        x1 = (x + width) * scale_x
        y1 = (y + height) * scale_y

        words.append(
            {
                "text": word,
                "bbox": [
                    x0,
                    y0,
                    x1,
                    y1,
                ],
                "confidence": confidence,
            }
        )

        text_parts.append(word)

    return {
        "text": " ".join(text_parts),
        "words": words,
        "ocr_language": language,
    }


def extract_pdf_text(
    pdf_bytes: bytes,
    language: str = DEFAULT_OCR_LANGUAGE,
    min_native_text_length: int = MIN_NATIVE_TEXT_LENGTH,
) -> dict[str, Any]:
    """
    Extract text from a PDF, using OCR when a page has little native text.

    Returns combined text and per-page word bounding boxes in PDF
    coordinates. Pages are numbered starting at 1.

    OCR boxes are estimates and must be validated before irreversible
    redaction.
    """

    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise ValueError("PDF input must be non-empty bytes.")

    if not isinstance(language, str) or not language.strip():
        raise ValueError("OCR language must be a non-empty string.")

    if min_native_text_length < 0:
        raise ValueError(
            "Minimum native text length cannot be negative."
        )

    pages_result = []
    document_text = []

    try:
        with pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf",
        ) as document:

            for page_index, page in enumerate(document):
                native_text = page.get_text("text").strip()

                if len(native_text) >= min_native_text_length:
                    page_text = native_text
                    words = _native_page_words(page)
                    source = "native"
                    used_language = None

                else:
                    try:
                        ocr_result = _ocr_page(
                            page,
                            language=language,
                        )

                    except pytesseract.TesseractNotFoundError as exc:
                        raise RuntimeError(
                            "Tesseract executable was not found. "
                            "Check pytesseract.pytesseract.tesseract_cmd."
                        ) from exc

                    except pytesseract.TesseractError as exc:
                        raise RuntimeError(
                            f"OCR failed on PDF page {page_index + 1}. "
                            f"Check whether language data for "
                            f"{language!r} is installed."
                        ) from exc

                    ocr_text = ocr_result["text"].strip()

                    page_text = ocr_text or native_text

                    words = (
                        ocr_result["words"]
                        if ocr_text
                        else _native_page_words(page)
                    )

                    source = (
                        "ocr"
                        if ocr_text
                        else (
                            "native_fallback"
                            if native_text
                            else "ocr_empty"
                        )
                    )

                    used_language = (
                        language if ocr_text else None
                    )

                pages_result.append(
                    {
                        "page_number": page_index + 1,
                        "source": source,
                        "text": page_text,
                        "words": words,
                        "ocr_language": used_language,
                    }
                )

                document_text.append(page_text)

    except pymupdf.FileDataError as exc:
        raise ValueError(
            "The uploaded file is not a readable PDF."
        ) from exc

    except pymupdf.EmptyFileError as exc:
        raise ValueError(
            "The uploaded PDF is empty."
        ) from exc

    return {
        "text": "\n".join(document_text),
        "pages": pages_result,
        "page_count": len(pages_result),
        "ocr_language": language,
        "tesseract_path": (
            pytesseract.pytesseract.tesseract_cmd
        ),
    }


def extract_pdf_text_from_file(
    path: str,
    language: str = DEFAULT_OCR_LANGUAGE,
) -> dict[str, Any]:
    """Convenience wrapper for local development and testing."""

    with open(path, "rb") as pdf_file:
        return extract_pdf_text(
            pdf_file.read(),
            language=language,
        )

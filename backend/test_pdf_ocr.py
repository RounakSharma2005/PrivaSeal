
"""Tests for native PDF extraction and scanned-page OCR."""

import io

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from backend.pii.pdf_ocr import extract_pdf_text


def make_native_pdf() -> bytes:
    """Create a PDF containing an ordinary searchable text layer."""
    buffer = io.BytesIO()

    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text(
            (60, 80),
            "Customer PAN: ABCDE1234F",
            fontsize=18,
        )
        page.insert_text(
            (60, 115),
            "Please review this customer document.",
            fontsize=12,
        )
        doc.save(buffer)

    return buffer.getvalue()


def make_scanned_pdf() -> bytes:
    """Create a PDF containing an image instead of searchable text."""
    image = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(image)

    font = None

    for font_path in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ):
        try:
            font = ImageFont.truetype(font_path, 56)
            break
        except OSError:
            continue

    if font is None:
        font = ImageFont.load_default(size=56)

    draw.text(
        (45, 90),
        "Customer PAN ABCDE1234F",
        fill="black",
        font=font,
    )

    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")

    pdf_buffer = io.BytesIO()

    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=150)
        page.insert_image(
            page.rect,
            stream=image_buffer.getvalue(),
        )
        doc.save(pdf_buffer)

    return pdf_buffer.getvalue()


def test_native_pdf_uses_text_extraction():
    result = extract_pdf_text(make_native_pdf())

    assert result["page_count"] == 1
    assert result["pages"][0]["source"] == "native"
    assert "ABCDE1234F" in result["text"]
    assert result["pages"][0]["words"]


def test_scanned_pdf_uses_ocr():
    result = extract_pdf_text(make_scanned_pdf())

    assert result["page_count"] == 1
    assert result["pages"][0]["source"] == "ocr"
    assert "ABCDE1234F" in result["text"].replace(" ", "")
    assert result["pages"][0]["words"]


def test_ocr_word_boxes_are_inside_pdf_page():
    pdf_bytes = make_scanned_pdf()
    result = extract_pdf_text(pdf_bytes)

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        page_rect = doc[0].rect

        assert result["pages"][0]["words"]

        for word in result["pages"][0]["words"]:
            x0, y0, x1, y1 = word["bbox"]

            assert 0 <= x0 <= x1 <= page_rect.width
            assert 0 <= y0 <= y1 <= page_rect.height
            assert word["text"].strip()


def test_empty_pdf_input_is_rejected():
    try:
        extract_pdf_text(b"")
        assert False, "Expected ValueError for empty input"
    except ValueError as exc:
        assert "empty" in str(exc).lower()

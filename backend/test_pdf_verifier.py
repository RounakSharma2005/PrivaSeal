
"""Tests for PDF redaction verification."""

import io

import pymupdf

from backend.pii.pdf_verifier import verify_redacted_pdf


def make_pdf(text: str) -> bytes:
    """Create a small in-memory PDF for verification tests."""
    doc = pymupdf.open()

    page = doc.new_page()
    page.insert_text((72, 72), text)

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    return output.getvalue()


def redact_text(pdf_bytes: bytes, target: str) -> bytes:
    """Apply a real PyMuPDF redaction and return saved PDF bytes."""
    doc = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    for page in doc:
        for rect in page.search_for(target):
            page.add_redact_annot(rect, fill=(0, 0, 0))

        page.apply_redactions()

    output = io.BytesIO()

    doc.save(
        output,
        garbage=4,
        deflate=True,
    )

    doc.close()

    return output.getvalue()


def test_verifier_detects_unredacted_text():
    original = make_pdf("Customer PAN ABCDE1234F")

    report = verify_redacted_pdf(
        original,
        ["ABCDE1234F"],
    )

    assert report["verified"] is False

    assert any(
        finding["location"] == "page_text"
        for finding in report["findings"]
    )


def test_verifier_passes_after_text_redaction():
    original = make_pdf("Customer PAN ABCDE1234F")
    redacted = redact_text(original, "ABCDE1234F")

    report = verify_redacted_pdf(
        redacted,
        ["ABCDE1234F"],
    )

    assert report["checks"]["extracted_text"]["passed"] is True


def test_verifier_detects_sensitive_metadata():
    doc = pymupdf.open()

    page = doc.new_page()
    page.insert_text((72, 72), "Sample document")

    doc.set_metadata(
        {"author": "ABCDE1234F"}
    )

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    report = verify_redacted_pdf(
        output.getvalue(),
        ["ABCDE1234F"],
    )

    assert report["checks"]["metadata"]["passed"] is False

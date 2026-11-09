
"""Tests for non-page-content PDF sanitization."""

import io

import pymupdf

from backend.pii.pdf_sanitizer import sanitize_pdf


def make_pdf_with_metadata() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Synthetic customer document")

    doc.set_metadata({
        "author": "SYNTHETIC_SECRET_12345",
        "title": "Synthetic document",
    })

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    return output.getvalue()


def make_pdf_with_attachment() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Synthetic document")

    doc.embfile_add(
        "sensitive.txt",
        b"SYNTHETIC_SECRET_12345",
    )

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    return output.getvalue()


def make_pdf_with_bookmark() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Synthetic document")

    doc.set_toc([
        [1, "SYNTHETIC_SECRET_12345", 1],
    ])

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    return output.getvalue()


def test_sanitizer_clears_metadata():
    original = make_pdf_with_metadata()

    sanitized, summary = sanitize_pdf(original)

    with pymupdf.open(
        stream=sanitized,
        filetype="pdf",
    ) as doc:
        metadata = doc.metadata or {}

        assert not metadata.get("author")
        assert not metadata.get("title")

    assert summary["metadata_cleared"] is True


def test_sanitizer_removes_embedded_attachments():
    original = make_pdf_with_attachment()

    sanitized, summary = sanitize_pdf(original)

    with pymupdf.open(
        stream=sanitized,
        filetype="pdf",
    ) as doc:
        assert doc.embfile_names() == []

    assert summary["attachments_removed"] == 1


def test_sanitizer_removes_bookmarks():
    original = make_pdf_with_bookmark()

    sanitized, summary = sanitize_pdf(original)

    with pymupdf.open(
        stream=sanitized,
        filetype="pdf",
    ) as doc:
        assert doc.get_toc() == []

    assert summary["bookmarks_removed"] is True


def test_sanitizer_preserves_page_content():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Safe synthetic content")

    output = io.BytesIO()
    doc.save(output)
    doc.close()

    sanitized, _ = sanitize_pdf(output.getvalue())

    with pymupdf.open(
        stream=sanitized,
        filetype="pdf",
    ) as result:
        assert "Safe synthetic content" in result[0].get_text()


def test_sanitizer_rejects_empty_input():
    try:
        sanitize_pdf(b"")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "non-empty" in str(exc)

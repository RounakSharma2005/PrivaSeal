
"""PDF sanitization utilities for Conseal.

Removes common non-page-content sources of sensitive information.
This is a defense-in-depth step, not a guarantee of complete PDF security.
"""

from __future__ import annotations

import io
from typing import Any

import pymupdf


def sanitize_pdf(pdf_bytes: bytes) -> tuple[bytes, dict[str, Any]]:
    """Remove attachments, annotations, widgets, bookmarks and metadata.

    Existing page redactions must be applied before calling this function.
    The function returns the sanitized PDF bytes and an audit summary.
    """

    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise ValueError("PDF input must be non-empty bytes.")

    summary: dict[str, Any] = {
        "attachments_removed": 0,
        "annotations_removed": 0,
        "form_fields_removed": 0,
        "links_removed": 0,
        "bookmarks_removed": False,
        "metadata_cleared": False,
        "xmp_metadata_cleared": False,
    }

    try:
        with pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf",
        ) as doc:

            if doc.is_encrypted:
                raise ValueError(
                    "Encrypted PDFs must be unlocked before sanitization."
                )

            # 1. Remove embedded files.
            for name in list(doc.embfile_names()):
                doc.embfile_del(name)
                summary["attachments_removed"] += 1

            # 2. Remove annotations, form widgets and links.
            for page in doc:
                # Remove annotations and comments.
                annotations = list(page.annots() or [])

                for annotation in annotations:
                    page.delete_annot(annotation)
                    summary["annotations_removed"] += 1

                # Remove interactive form fields.
                widgets = list(page.widgets() or [])

                for widget in widgets:
                    page.delete_widget(widget)
                    summary["form_fields_removed"] += 1

                # Remove hyperlinks and their destinations.
                links = page.get_links()

                for link in links:
                    page.delete_link(link)
                    summary["links_removed"] += 1

            # 3. Remove bookmarks / table of contents.
            doc.set_toc([])
            summary["bookmarks_removed"] = True

            # 4. Clear standard metadata.
            doc.set_metadata({
                "title": "",
                "author": "",
                "subject": "",
                "keywords": "",
                "creator": "",
                "producer": "",
                "creationDate": "",
                "modDate": "",
                "trapped": "",
            })
            summary["metadata_cleared"] = True

            # 5. Clear XMP metadata.
            try:
                doc.del_xml_metadata()
                summary["xmp_metadata_cleared"] = True
            except (AttributeError, RuntimeError):
                summary["xmp_metadata_cleared"] = False

            # 6. Save a compacted copy, dropping unreferenced objects.
            output = io.BytesIO()

            doc.save(
                output,
                garbage=4,
                deflate=True,
                clean=True,
            )

            sanitized_bytes = output.getvalue()

        if not sanitized_bytes:
            raise RuntimeError("PDF sanitization produced an empty file.")

        return sanitized_bytes, summary

    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ValueError("Input is not a readable PDF.") from exc

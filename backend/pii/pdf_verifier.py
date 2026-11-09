
"""Independent post-export verification for redacted PDFs.

Checks common PDF content locations, including native text, OCR-extracted
image text, metadata, annotations, form fields, bookmarks and attachments.

This is a verification aid, not a guarantee of complete anonymization.
"""

from __future__ import annotations

import io
from typing import Any, Iterable

import pymupdf

from .pdf_ocr import extract_pdf_text


def _normalise(value: str) -> str:
    """Normalize whitespace and case for basic leak detection."""
    return " ".join(value.casefold().split())


def _contains_sensitive_value(
    content: str,
    sensitive_values: list[str],
) -> list[str]:
    """Return supplied values found in a content string."""
    normalized_content = _normalise(content)

    return [
        value
        for value in sensitive_values
        if _normalise(value) in normalized_content
    ]


def _decode_bytes(data: bytes) -> str:
    """Decode likely text content without assuming a particular encoding."""
    return data.decode("utf-8", errors="ignore")


def _inspect_embedded_pdf(
    data: bytes,
    sensitive_values: list[str],
    depth: int = 0,
) -> list[dict[str, Any]]:
    """Inspect text in an embedded PDF, with a recursion limit."""
    findings: list[dict[str, Any]] = []

    if depth > 2:
        return findings

    try:
        with pymupdf.open(
            stream=data,
            filetype="pdf",
        ) as embedded_doc:

            for page_number, page in enumerate(
                embedded_doc,
                start=1,
            ):
                leaked = _contains_sensitive_value(
                    page.get_text(),
                    sensitive_values,
                )

                if leaked:
                    findings.append({
                        "location": "embedded_pdf_page",
                        "page": page_number,
                        "values_found": leaked,
                    })

            for name in embedded_doc.embfile_names():
                try:
                    nested = embedded_doc.embfile_get(name)

                    findings.extend(
                        _inspect_embedded_pdf(
                            nested,
                            sensitive_values,
                            depth + 1,
                        )
                    )

                except Exception:
                    findings.append({
                        "location": "nested_embedded_file",
                        "name": name,
                        "status": "not_fully_inspected",
                    })

    except Exception:
        # The attachment may not be a PDF.
        pass

    return findings


def verify_redacted_pdf(
    pdf_bytes: bytes,
    sensitive_values: Iterable[str],
) -> dict[str, Any]:
    """Check common PDF locations for supplied sensitive values.

    Image-based text is checked through OCR. Only supplied values are
    searched for; unknown or transformed identifiers may be missed.
    """

    values = sorted({
        value.strip()
        for value in sensitive_values
        if isinstance(value, str) and len(value.strip()) >= 4
    })

    report: dict[str, Any] = {
        "verified": False,
        "checks": {},
        "findings": [],
        "limitations": [
            "OCR can fail to recognize text because of image quality, "
            "font, rotation, language or layout.",
            "Only supplied sensitive values are searched for.",
            "Encrypted or unsupported embedded content may not be inspected.",
            "This verification does not prove complete anonymization.",
        ],
    }

    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        report["checks"]["pdf_open"] = {
            "passed": False,
            "error": "PDF input must be non-empty bytes.",
        }
        return report

    try:
        with pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf",
        ) as doc:

            # 1. Native extracted page text.
            text_findings = []

            for page_number, page in enumerate(doc, start=1):
                leaked = _contains_sensitive_value(
                    page.get_text(),
                    values,
                )

                if leaked:
                    text_findings.append({
                        "location": "page_text",
                        "page": page_number,
                        "values_found": leaked,
                    })

            report["checks"]["extracted_text"] = {
                "passed": not text_findings,
                "description": (
                    "Searches native extracted page text."
                ),
            }

            report["findings"].extend(text_findings)

            # 2. OCR verification of scanned/image-based pages.
            try:
                extraction = extract_pdf_text(pdf_bytes)

                ocr_findings = []

                for page in extraction["pages"]:
                    if page["source"] != "ocr":
                        continue

                    leaked = _contains_sensitive_value(
                        page["text"],
                        values,
                    )

                    if leaked:
                        ocr_findings.append({
                            "location": "ocr_text",
                            "page": page["page_number"],
                            "values_found": leaked,
                        })

                report["checks"]["ocr_text"] = {
                    "passed": not ocr_findings,
                    "description": (
                        "Searches OCR-extracted text from scanned pages."
                    ),
                    "pages_checked": sum(
                        1
                        for page in extraction["pages"]
                        if page["source"] == "ocr"
                    ),
                }

                report["findings"].extend(ocr_findings)

            except Exception as exc:
                report["checks"]["ocr_text"] = {
                    "passed": False,
                    "status": "not_fully_inspected",
                    "error": type(exc).__name__,
                }

            # 3. Standard metadata and XMP metadata.
            metadata_text = repr(doc.metadata or {})
            metadata_inspection_succeeded = True

            try:
                metadata_text += "\n" + (
                    doc.get_xml_metadata() or ""
                )
            except Exception:
                metadata_inspection_succeeded = False

            metadata_leaks = _contains_sensitive_value(
                metadata_text,
                values,
            )

            report["checks"]["metadata"] = {
                "passed": (
                    metadata_inspection_succeeded
                    and not metadata_leaks
                ),
                "status": (
                    "inspected"
                    if metadata_inspection_succeeded
                    else "not_fully_inspected"
                ),
            }

            if metadata_leaks:
                report["findings"].append({
                    "location": "metadata",
                    "values_found": metadata_leaks,
                })

            # 4. Annotations and their contents.
            annotation_findings = []

            for page_number, page in enumerate(doc, start=1):
                annotation = page.first_annot

                while annotation:
                    annotation_text = repr(
                        annotation.info or {}
                    )

                    leaked = _contains_sensitive_value(
                        annotation_text,
                        values,
                    )

                    if leaked:
                        annotation_findings.append({
                            "location": "annotation",
                            "page": page_number,
                            "values_found": leaked,
                        })

                    annotation = annotation.next

            report["checks"]["annotations"] = {
                "passed": not annotation_findings,
            }

            report["findings"].extend(annotation_findings)

            # 5. Interactive form fields.
            form_findings = []

            for page_number, page in enumerate(doc, start=1):
                for widget in page.widgets() or []:
                    field_text = " ".join([
                        str(widget.field_name or ""),
                        str(widget.field_value or ""),
                    ])

                    leaked = _contains_sensitive_value(
                        field_text,
                        values,
                    )

                    if leaked:
                        form_findings.append({
                            "location": "form_field",
                            "page": page_number,
                            "field_name": widget.field_name,
                            "values_found": leaked,
                        })

            report["checks"]["form_fields"] = {
                "passed": not form_findings,
            }

            report["findings"].extend(form_findings)

            # 6. Bookmarks and table of contents.
            toc_text = repr(doc.get_toc())

            toc_leaks = _contains_sensitive_value(
                toc_text,
                values,
            )

            report["checks"]["bookmarks"] = {
                "passed": not toc_leaks,
            }

            if toc_leaks:
                report["findings"].append({
                    "location": "bookmarks",
                    "values_found": toc_leaks,
                })

            # 7. Embedded files.
            embedded_findings = []
            embedded_names = doc.embfile_names()

            for name in embedded_names:
                name_leaks = _contains_sensitive_value(
                    name,
                    values,
                )

                if name_leaks:
                    embedded_findings.append({
                        "location": "embedded_file_name",
                        "name": name,
                        "values_found": name_leaks,
                    })

                try:
                    embedded_data = doc.embfile_get(name)

                    embedded_text = _decode_bytes(
                        embedded_data
                    )

                    content_leaks = _contains_sensitive_value(
                        embedded_text,
                        values,
                    )

                    if content_leaks:
                        embedded_findings.append({
                            "location": "embedded_file_content",
                            "name": name,
                            "values_found": content_leaks,
                        })

                    embedded_findings.extend(
                        _inspect_embedded_pdf(
                            embedded_data,
                            values,
                        )
                    )

                except Exception:
                    embedded_findings.append({
                        "location": "embedded_file",
                        "name": name,
                        "status": "not_fully_inspected",
                    })

            report["checks"]["embedded_files"] = {
                "passed": not embedded_findings,
                "files_found": len(embedded_names),
                "status": (
                    "inspected"
                    if not embedded_findings
                    else "findings_or_incomplete_inspection"
                ),
            }

            report["findings"].extend(embedded_findings)

            # A passing result means all implemented checks passed.
            report["verified"] = all(
                check.get("passed", False)
                for check in report["checks"].values()
            )

    except Exception as exc:
        report["checks"]["pdf_open"] = {
            "passed": False,
            "error": type(exc).__name__,
        }

        report["verified"] = False

    return report

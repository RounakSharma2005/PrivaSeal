
"""End-to-end API tests for scanned PDF processing."""

import io
import json
import zipfile
import pymupdf
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from backend.main import app


client = TestClient(app)


TEST_PAN = "ABCDE1234F"


def make_scanned_pdf() -> bytes:
    """Create a synthetic scanned PDF containing a test PAN."""

    image = Image.new("RGB", (1600, 400), "white")
    draw = ImageDraw.Draw(image)

    font = None

    for font_path in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ):
        try:
            font = ImageFont.truetype(font_path, 90)
            break
        except OSError:
            continue

    if font is None:
        font = ImageFont.load_default(size=90)

    draw.text(
        (60, 140),
        f"Customer PAN: {TEST_PAN}",
        fill="black",
        font=font,
    )

    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")

    pdf_buffer = io.BytesIO()

    with pymupdf.open() as doc:
        page = doc.new_page(width=800, height=200)

        page.insert_image(
            page.rect,
            stream=image_buffer.getvalue(),
        )

        doc.save(pdf_buffer)

    return pdf_buffer.getvalue()


def test_scanned_pdf_upload_api():
    """Verify that the upload endpoint extracts scanned PDF text."""

    pdf_bytes = make_scanned_pdf()

    response = client.post(
        "/pii/upload",
        files={
            "file": (
                "synthetic_customer.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200, (
    f"PDF export failed with {response.status_code}: "
    f"{response.text}"
)

    result = response.json()

    assert result["original_text"].strip()
    assert TEST_PAN in result["original_text"].replace(" ", "")


def test_scanned_pdf_redaction_api():
    """Verify that scanned image text is permanently redacted."""

    pdf_bytes = make_scanned_pdf()

    response = client.post(
        "/pii/export_pdf",
        files={
            "file": (
                "synthetic_customer.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
        data={
            "redactions_json": json.dumps([
                {
                    "value": TEST_PAN,
                    "type": "PAN",
                    "action": "redact",
                }
            ])
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers.get("x-redaction-verified") == "true"

    exported_pdf = response.content

    assert exported_pdf

    # Verify the exported PDF can still be opened.
    with pymupdf.open(
        stream=exported_pdf,
        filetype="pdf",
    ) as doc:
        assert len(doc) == 1

        # The original scanned page should still contain an image.
        assert doc[0].get_images()


def test_scanned_pdf_redaction_does_not_return_original_text():
    """Check that the exported scanned PDF no longer exposes the PAN."""

    pdf_bytes = make_scanned_pdf()

    response = client.post(
        "/pii/export_pdf",
        files={
            "file": (
                "synthetic_customer.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
        data={
            "redactions_json": json.dumps([
                {
                    "value": TEST_PAN,
                    "type": "PAN",
                    "action": "redact",
                }
            ])
        },
    )

    
    assert response.status_code == 200, (
    f"PDF export failed with {response.status_code}: "
    f"{response.text}"
)

    from backend.pii.pdf_ocr import extract_pdf_text

    verification = extract_pdf_text(response.content)

    extracted_text = verification["text"].replace(" ", "")

    assert TEST_PAN not in extracted_text

def test_scanned_pdf_evidence_export_api():
    """Verify PDF and privacy evidence are returned together."""

    pdf_bytes = make_scanned_pdf()

    response = client.post(
        "/pii/export_pdf",
        files={
            "file": (
                "synthetic_customer.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
        data={
            "redactions_json": json.dumps([
                {
                    "value": TEST_PAN,
                    "type": "PAN",
                    "action": "redact",
                }
            ]),
            "include_evidence": "true",
        },
    )

    assert response.status_code == 200, (
        f"Evidence export failed: {response.status_code}: "
        f"{response.text}"
    )

    assert "application/zip" in response.headers["content-type"]
    assert response.headers.get("x-redaction-verified") == "true"

    # Inspect the returned ZIP archive.
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()

        assert "privacy_evidence_report.json" in names

        pdf_files = [
            name for name in names
            if name.lower().endswith(".pdf")
        ]
        assert len(pdf_files) == 1

        report = json.loads(
            archive.read("privacy_evidence_report.json")
        )

        exported_pdf = archive.read(pdf_files[0])

    # Verify evidence report structure.
    assert report["report_version"] == "1.0"
    assert report["processing"]["document_type"] == "PDF"
    assert report["verification"]["performed"] is True
    assert report["verification"]["verified"] is True
    assert report["privacy"]["contains_raw_pii"] is False
    assert report["privacy"]["contains_original_document_text"] is False

    # Ensure the sensitive PAN is not leaked into the report.
    report_text = json.dumps(report)

    assert TEST_PAN not in report_text
    assert "Customer PAN" not in report_text

    # Ensure the exported PDF remains valid.
    with pymupdf.open(
        stream=exported_pdf,
        filetype="pdf",
    ) as doc:
        assert len(doc) == 1
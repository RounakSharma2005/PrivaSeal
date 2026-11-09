
import pytest

from fastapi import HTTPException, UploadFile
from io import BytesIO

from backend.pii_route import validate_pdf_upload


def make_upload(filename, content):
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
    )


@pytest.mark.asyncio
async def test_valid_pdf_upload():
    content = b"%PDF-1.7\nvalid test content"

    upload = make_upload("document.pdf", content)

    result = await validate_pdf_upload(upload)

    assert result == content


@pytest.mark.asyncio
async def test_reject_unsupported_extension():
    upload = make_upload("document.txt", b"%PDF-1.7")

    with pytest.raises(HTTPException) as exc:
        await validate_pdf_upload(upload)

    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_reject_invalid_pdf_signature():
    upload = make_upload("document.pdf", b"This is not a PDF")

    with pytest.raises(HTTPException) as exc:
        await validate_pdf_upload(upload)

    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_reject_empty_upload():
    upload = make_upload("empty.pdf", b"")

    with pytest.raises(HTTPException) as exc:
        await validate_pdf_upload(upload)

    assert exc.value.status_code == 400

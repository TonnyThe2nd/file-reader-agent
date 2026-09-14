"""Native OCR integration; skipped where Tesseract and optional packages are absent."""

import importlib.util
import shutil
from io import BytesIO

import pytest

from app.core.config import settings
from app.services.document_service import split_document


@pytest.mark.parametrize("mime", ["image/png", "application/pdf"])
def test_native_scanned_document_ocr(mime, monkeypatch):
    if not shutil.which("tesseract") or any(
        importlib.util.find_spec(name) is None for name in ("PIL", "pypdfium2", "pytesseract")
    ):
        pytest.skip("Native OCR dependencies are not installed")
    from PIL import Image, ImageDraw, ImageFont

    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_languages", "eng")
    with Image.new("RGB", (1000, 160), "white") as image:
        ImageDraw.Draw(image).text(
            (30, 30), "DOCUMENT TEST 12345", font=ImageFont.load_default(size=48), fill="black"
        )
        buffer = BytesIO()
        image.save(buffer, format="PDF" if mime == "application/pdf" else "PNG")
    sections = split_document(buffer.getvalue(), mime)
    assert "12345" in " ".join(text for _, text in sections)
    assert sections[0][0] == ("Pagina 1" if mime == "application/pdf" else "Imagem")

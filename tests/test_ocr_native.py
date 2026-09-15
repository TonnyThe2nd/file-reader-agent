"""Native OCR integration; skipped where Tesseract and optional packages are absent."""

import importlib.util
import shutil
from io import BytesIO

import pytest

from app.core.config import settings
from app.services import ocr_service
from app.services.document_service import split_document


def test_pdf_rasterization_without_tesseract(monkeypatch):
    pytest.importorskip("pypdfium2")
    Image = pytest.importorskip("PIL.Image")
    monkeypatch.setattr(settings, "ocr_enabled", True)
    rendered = []

    def recognize(image):
        rendered.append(image.size)
        assert image.getpixel((0, 0)) == (255, 255, 255)
        return "Texto reconhecido 12345"

    monkeypatch.setattr(ocr_service, "extract_image", recognize)
    buffer = BytesIO()
    with Image.new("RGB", (100, 80), "white") as image:
        image.save(buffer, format="PDF")
    assert split_document(buffer.getvalue(), "application/pdf") == [
        ("Pagina 1", "Texto reconhecido 12345")
    ]
    assert rendered == [(200, 160)]


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

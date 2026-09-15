"""Local OCR with page, pixel and subprocess time limits."""

from contextlib import closing
from io import BytesIO
from threading import Lock

from fastapi import HTTPException

from app.core.config import settings

_pdf_lock = Lock()


def extract_image(image):
    import pytesseract

    if image.width * image.height > 20_000_000:
        raise HTTPException(413, "Imagem excede o limite de 20 megapixels para OCR.")
    return pytesseract.image_to_string(
        image, lang=settings.ocr_languages, timeout=settings.ocr_timeout_seconds
    )


def ocr_pages(content: bytes, mime_type: str, page_numbers=None):
    if not settings.ocr_enabled:
        raise HTTPException(422, "Documento requer OCR. Habilite OCR_ENABLED e instale Tesseract.")
    try:
        from PIL import Image

        if mime_type.startswith("image/"):
            with Image.open(BytesIO(content)) as image:
                return [("Imagem", extract_image(image))]
        import pypdfium2 as pdfium

        with _pdf_lock, pdfium.PdfDocument(content) as pdf:
            numbers = list(range(len(pdf))) if page_numbers is None else page_numbers
            if len(numbers) > settings.ocr_max_pages:
                raise HTTPException(413, "PDF excede o limite de paginas para OCR.")
            result = []
            for i in numbers:
                with closing(pdf[i]) as page:
                    width, height = page.get_size()
                    if width * height * 4 > 20_000_000:
                        raise HTTPException(413, "Pagina excede o limite de pixels para OCR.")
                    with closing(page.render(scale=2)) as bitmap:
                        with bitmap.to_pil() as image:
                            result.append((f"Pagina {i + 1}", extract_image(image)))
            return result
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(503, "Dependencias de OCR nao instaladas.") from None
    except Exception:
        raise HTTPException(
            422, "Falha no OCR. Verifique o arquivo, Tesseract e os idiomas instalados."
        ) from None

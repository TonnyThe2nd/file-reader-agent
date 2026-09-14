import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.models import Document, DocumentChunk
from app.services.document_service import split_document
from app.worker import claim, process_one


class Embeddings:
    async def embed(self, texts, task):
        return [[1.0, 0.0] for _ in texts]


def test_worker_claim_process_and_retry(client, database):
    row = client.post("/documents", files={"file": ("a.txt", b"Conteudo para indexar")}).json()
    assert row["processing_status"] == "pending"
    assert asyncio.run(process_one(Embeddings(), database))
    result = client.get("/documents/" + row["id"]).json()
    assert result["processing_status"] == "ready"
    assert result["processing_progress"] == 100
    assert not asyncio.run(process_one(Embeddings(), database))
    assert client.post("/documents/" + row["id"] + "/retry").status_code == 409
    with database() as db:
        assert db.scalar(select(DocumentChunk)).content == "Conteudo para indexar"


def test_expired_lease_can_be_reclaimed(client, database):
    row = client.post("/documents", files={"file": ("a.txt", b"Conteudo")}).json()
    first = claim(database)
    assert first and claim(database) is None
    with database() as db:
        document = db.get(Document, UUID(row["id"]))
        document.processing_available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    second = claim(database)
    assert second[0] == first[0] and second[1] != first[1]


def test_permanent_failure_and_manual_retry(client, database):
    from fastapi import HTTPException

    class Invalid:
        async def embed(self, texts, task):
            raise HTTPException(422, "Invalid model")

    row = client.post("/documents", files={"file": ("empty.txt", b"Conteudo")}).json()
    asyncio.run(process_one(Invalid(), database))
    assert client.get("/documents/" + row["id"]).json()["processing_status"] == "failed"
    assert (
        client.post("/documents/" + row["id"] + "/retry").json()["processing_status"] == "pending"
    )


def test_metadata_filters(client):
    row = client.post("/documents", files={"file": ("receita.txt", b"42")}).json()
    assert (
        client.patch("/documents/" + row["id"], json={"category": "financeiro"}).status_code == 200
    )
    assert (
        len(client.get("/documents?category=financeiro&mime_type=text/plain&search=receita").json())
        == 1
    )
    assert client.get("/documents?category=juridico").json() == []
    assert client.get("/documents?created_from=2099-01-01T00:00:00Z").json() == []


def test_image_ocr_and_scanned_pdf_fallback(monkeypatch):
    from io import BytesIO

    from pypdf import PdfWriter

    from app.services import ocr_service

    monkeypatch.setattr(settings, "ocr_enabled", True)
    calls = []

    def fake(content, mime, page_numbers=None):
        calls.append((mime, page_numbers))
        return [("Pagina 1" if page_numbers else "Imagem", "Texto reconhecido")]

    monkeypatch.setattr(ocr_service, "ocr_pages", fake)
    assert split_document(b"image", "image/png")[0][1] == "Texto reconhecido"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    assert split_document(buffer.getvalue(), "application/pdf")[0] == (
        "Pagina 1",
        "Texto reconhecido",
    )
    assert calls[-1] == ("application/pdf", [0])

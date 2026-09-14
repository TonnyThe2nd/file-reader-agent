"""Armazenamento por dono e indexacao reutilizavel por documento."""

import hashlib
import math
from io import BytesIO
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models import Document, DocumentChunk
from app.schemas.ask import Source

INDEX_VERSION = "chunks-v2"


def get_document(db: Session, document_id: UUID, owner: str, *, write=False) -> Document:
    from app.services.governance_service import accessible_documents

    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == owner if write else accessible_documents(db, owner),
        )
    )
    if document is None:
        raise HTTPException(404, "Documento nao encontrado.")
    return document


def save_document(db: Session, owner: str, name: str, content: bytes, mime_type: str) -> Document:
    digest = hashlib.sha256(content).hexdigest()
    query = select(Document).where(
        Document.owner_id == owner, Document.sha256 == digest, Document.mime_type == mime_type
    )
    document = db.scalar(query)
    if document is not None:
        return document
    from app.models.governance import UserPolicy
    from app.services.governance_service import audit, ensure_policy

    ensure_policy(db, owner)
    limits = db.scalar(select(UserPolicy).where(UserPolicy.owner_id == owner).with_for_update())
    # Another upload may have saved this same digest while we waited for the quota lock.
    document = db.scalar(query)
    if document is not None:
        db.commit()
        db.refresh(document)
        return document
    used = db.scalar(
        select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.owner_id == owner)
    )
    if used + len(content) > limits.storage_bytes:
        raise HTTPException(413, "Limite de armazenamento atingido.")
    document = Document(
        owner_id=owner,
        name=name[:255],
        sha256=digest,
        content=content,
        mime_type=mime_type,
        size_bytes=len(content),
    )
    db.add(document)
    audit(db, owner, "document.upload")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        document = db.scalar(query)
        if document is None:
            raise
    db.refresh(document)
    return document


def split_document(content: bytes, mime_type: str) -> list[tuple[str, str]]:
    if mime_type == "text/plain":
        try:
            pages = [("Texto", content.decode("utf-8-sig"))]
        except UnicodeDecodeError:
            raise HTTPException(422, "Arquivos de texto devem usar UTF-8.") from None
    elif mime_type == "application/pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("encrypted")
            if len(reader.pages) > 500:
                raise ValueError("too many pages")
            pages = [
                (f"Pagina {i + 1}", page.extract_text() or "")
                for i, page in enumerate(reader.pages)
            ]
        except Exception:
            raise HTTPException(
                422,
                "Nao foi possivel extrair texto do PDF. Use um PDF valido sem senha ou consulta direta.",
            ) from None
        missing = [i for i, (_, text) in enumerate(pages) if not text.strip()]
        if missing and settings.ocr_enabled:
            from app.services.ocr_service import ocr_pages

            for i, result in zip(missing, ocr_pages(content, mime_type, missing)):
                pages[i] = result
    elif mime_type.startswith("image/") and settings.ocr_enabled:
        from app.services.ocr_service import ocr_pages

        pages = ocr_pages(content, mime_type)
    else:
        raise HTTPException(
            422, "RAG aceita textos e PDFs com texto. Para imagens, use consulta direta."
        )
    chunks = []
    for section, text in pages:
        for offset in range(0, len(text), 1800):
            chunk = text[offset : offset + 2000].strip()
            if chunk:
                chunks.append((section, chunk))
                if len(chunks) > settings.rag_max_chunks:
                    raise HTTPException(
                        413,
                        "Documento muito extenso para o indice. Divida o arquivo ou use consulta direta.",
                    )
    if not chunks:
        raise HTTPException(
            422,
            "Documento sem texto extraivel. Use consulta direta para imagens e PDFs digitalizados.",
        )
    return chunks


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Vetores com dimensoes diferentes ou vazios")
    norm = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    return sum(a * b for a, b in zip(left, right)) / norm if norm else 0.0


async def index_document(db: Session, document: Document, ollama) -> list[DocumentChunk]:
    index_model = f"ollama:{settings.embedding_model_ollama}:{settings.ollama_embedding_dimensions}:{INDEX_VERSION}:nomic-v1"
    extraction = f"{settings.ocr_enabled}:{settings.ocr_languages}:{settings.redact_sensitive_data}"
    index_model += ":" + hashlib.sha256(extraction.encode()).hexdigest()[:8]
    query = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document.id, DocumentChunk.embedding_model == index_model
        )
        .order_by(DocumentChunk.position)
    )
    chunks = list(db.scalars(query))
    if not chunks:
        sections = await run_in_threadpool(split_document, document.content, document.mime_type)
        vectors = await ollama.embed([text for _, text in sections], "RETRIEVAL_DOCUMENT")
        chunks = [
            DocumentChunk(
                document_id=document.id,
                position=i,
                section=section,
                content=text,
                embedding_model=index_model,
                embedding=vector,
            )
            for i, ((section, text), vector) in enumerate(zip(sections, vectors))
        ]
        db.add_all(chunks)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            chunks = list(db.scalars(query))
            if not chunks:
                raise
    if document.processing_token is None:
        document.processing_status = "ready"
        document.processing_progress = 100
        document.processing_error = None
        db.commit()
    # Refresh in one query after commits, avoiding lazy SELECTs for each expired chunk.
    return list(db.scalars(query))


async def retrieve(db: Session, document: Document, question: str, ollama) -> list[Source]:
    chunks = await index_document(db, document, ollama)
    vector = (await ollama.embed([question], "RETRIEVAL_QUERY"))[0]
    ranked = sorted(
        ((cosine(vector, chunk.embedding), chunk) for chunk in chunks),
        key=lambda item: (-item[0], item[1].position),
    )[: settings.rag_top_k]
    return [
        Source(
            content=chunk.content,
            source=document.name,
            section=f"{chunk.section}, trecho {chunk.position + 1}",
            score=score,
        )
        for score, chunk in ranked
    ]

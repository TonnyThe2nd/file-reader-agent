"""Armazenamento por dono e índice vetorial exato limitado a um documento."""

import hashlib
import math
from io import BytesIO
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models import Document, DocumentChunk
from app.schemas.ask import Source

INDEX_VERSION = "chunks-v1"


def get_document(db: Session, document_id: UUID, owner: str) -> Document:
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.owner_id == owner)
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
    document = Document(
        owner_id=owner,
        name=name[:255],
        sha256=digest,
        content=content,
        mime_type=mime_type,
        size_bytes=len(content),
    )
    db.add(document)
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


async def retrieve(db: Session, document: Document, question: str, gemini) -> list[Source]:
    index_model = f"{settings.embedding_model}:{INDEX_VERSION}"
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
        vectors = await gemini.embed([text for _, text in sections], "RETRIEVAL_DOCUMENT")
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
    vector = (await gemini.embed([question], "RETRIEVAL_QUERY"))[0]
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

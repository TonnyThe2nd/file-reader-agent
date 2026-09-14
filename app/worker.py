import asyncio
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy import or_, select, update

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger, setup_logging
from app.models import Document
from app.services.document_service import index_document
from app.services.ollama_service import OllamaService
from app.services.retention_service import apply_retention


def claim(factory=SessionLocal):
    now = datetime.now(timezone.utc)
    eligible = (
        Document.processing_status.in_(["pending", "processing"]),
        or_(Document.processing_available_at.is_(None), Document.processing_available_at <= now),
        Document.processing_attempts < 3,
    )
    with factory() as db:
        row = db.scalar(
            select(Document)
            .where(*eligible)
            .order_by(Document.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        token = str(uuid4())
        result = db.execute(
            update(Document)
            .execution_options(synchronize_session=False)
            .where(Document.id == row.id, *eligible)
            .values(
                processing_status="processing",
                processing_token=token,
                processing_attempts=Document.processing_attempts + 1,
                processing_progress=10,
                processing_error=None,
                processing_available_at=now
                + timedelta(seconds=settings.worker_timeout_seconds + 120),
            )
        )
        db.commit()
        return (row.id, token) if result.rowcount else None


async def process_one(ollama, factory=SessionLocal):
    with factory() as db:
        db.execute(
            update(Document)
            .where(
                Document.processing_status == "processing",
                Document.processing_attempts >= 3,
                Document.processing_available_at <= datetime.now(timezone.utc),
            )
            .values(
                processing_status="failed",
                processing_error="Processamento interrompido. Tente novamente.",
            )
        )
        db.commit()
    job = claim(factory)
    if not job:
        return False
    document_id, token = job
    try:
        with factory() as db:
            document = db.get(Document, document_id)
            if document is None:
                return True
            await asyncio.wait_for(
                index_document(db, document, ollama), settings.worker_timeout_seconds
            )
        values = dict(
            processing_status="ready",
            processing_progress=100,
            processing_error=None,
            processing_available_at=None,
        )
    except Exception as exc:
        with factory() as db:
            document = db.get(Document, document_id)
            if document is None:
                return True
            retryable = getattr(exc, "status_code", 503) in (429, 500, 502, 503, 504)
            retry = retryable and document.processing_attempts < 3
            values = dict(
                processing_status="pending" if retry else "failed",
                processing_progress=0,
                processing_error="Falha temporaria; nova tentativa agendada."
                if retry
                else "Falha no processamento. Verifique o formato e o servico local.",
                processing_available_at=datetime.now(timezone.utc)
                + timedelta(seconds=30 * document.processing_attempts),
            )
    with factory() as db:
        db.execute(
            update(Document)
            .where(Document.id == document_id, Document.processing_token == token)
            .values(**values)
        )
        db.commit()
    return True


async def main():
    setup_logging()
    last_retention = 0.0
    async with httpx.AsyncClient() as client:
        while True:
            try:
                if time.monotonic() - last_retention >= 60:
                    with SessionLocal() as db:
                        apply_retention(db, dry_run=False)
                    last_retention = time.monotonic()
                worked = await process_one(OllamaService(client, settings))
            except Exception:
                get_logger(__name__).error("Falha de infraestrutura no worker")
                worked = False
            if not worked:
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())

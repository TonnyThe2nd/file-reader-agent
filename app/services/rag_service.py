import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import CACHE_HITS_TOTAL, GENERATION_TOKENS_TOTAL
from app.models import Interaction
from app.schemas.ask import AskResponse
from app.services.document_service import INDEX_VERSION, get_document, retrieve, save_document
from app.services.gemini_service import GeminiService

PROMPT_VERSION = "grounded-v2"


class RAGService:
    def __init__(self, gemini: GeminiService):
        self.gemini = gemini

    async def ask(
        self,
        question: str,
        db: Session,
        owner: str,
        *,
        content: bytes | None = None,
        mime_type: str | None = None,
        filename: str = "documento",
        document_id: UUID | None = None,
        mode: str = "direct",
        use_cache: bool = True,
    ) -> AskResponse:
        start = time.perf_counter()
        document = (
            get_document(db, document_id, owner)
            if document_id
            else save_document(db, owner, filename, content, mime_type)
        )
        if mode == "rag" and document.mime_type not in ("text/plain", "application/pdf"):
            raise HTTPException(422, "RAG aceita textos e PDFs. Use consulta direta para imagens.")
        signature = [
            owner,
            str(document.id),
            document.sha256,
            question,
            mode,
            settings.gemini_model,
            settings.embedding_model,
            settings.rag_top_k,
            INDEX_VERSION,
            PROMPT_VERSION,
        ]
        cache_key = hashlib.sha256(json.dumps(signature, ensure_ascii=False).encode()).hexdigest()
        cached = None
        if use_cache and settings.cache_ttl_seconds:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.cache_ttl_seconds)
            cached = db.scalar(
                select(Interaction)
                .where(
                    Interaction.owner_id == owner,
                    Interaction.cache_key == cache_key,
                    Interaction.cache_hit.is_(False),
                    Interaction.created_at >= cutoff,
                )
                .order_by(Interaction.created_at.desc())
                .limit(1)
            )
        sources = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        if cached:
            answer, model, sources = cached.answer, cached.model_used, cached.sources
            CACHE_HITS_TOTAL.inc()
        else:
            prompt, payload, mime = question, document.content, document.mime_type
            if mode == "rag":
                retrieved = await retrieve(db, document, question, self.gemini)
                sources = [source.model_dump() for source in retrieved]
                payload = "\n\n".join(
                    f"[{i + 1}] {s.source} — {s.section}\n{s.content}"
                    for i, s in enumerate(retrieved)
                ).encode("utf-8")
                mime = "text/plain"
                prompt = (
                    question
                    + "\nResponda apenas com base nos trechos fornecidos e cite seus numeros [1], [2], etc. Se nao houver evidencia suficiente, informe isso."
                )
            answer, model = await self.gemini.generate(prompt, payload, mime)
            usage = self.gemini.usage
            for kind, value in usage.items():
                GENERATION_TOKENS_TOTAL.labels(kind=kind).inc(value)
        row = Interaction(
            owner_id=owner,
            document_id=document.id,
            question=question,
            answer=answer,
            sources=sources,
            latency_ms=(time.perf_counter() - start) * 1000,
            model_used=model,
            cache_hit=cached is not None,
            cache_key=cache_key,
            mode=mode,
            **usage,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return AskResponse(
            interaction_id=str(row.id),
            answer=row.answer,
            sources=row.sources,
            latency_ms=row.latency_ms,
            model_used=row.model_used,
            cache_hit=row.cache_hit,
            created_at=row.created_at,
            document_id=str(document.id),
            mode=mode,
            **usage,
        )

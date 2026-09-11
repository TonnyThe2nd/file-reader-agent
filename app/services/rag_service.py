import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import CACHE_HITS_TOTAL, GENERATION_TOKENS_TOTAL
from app.models import Interaction
from app.models.conversation import Conversation
from app.schemas.ask import AskResponse
from app.services.conversation_service import get_conversation, memory
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
        conversation_id: UUID | None = None,
        chat: bool = False,
    ) -> AskResponse:
        start = time.perf_counter()
        conversation = get_conversation(db, conversation_id, owner) if conversation_id else None
        if conversation:
            if not conversation.document_id:
                raise HTTPException(
                    410, "O documento desta conversa foi excluido. Inicie outra conversa."
                )
            document_id = conversation.document_id
        document = (
            get_document(db, document_id, owner)
            if document_id
            else save_document(db, owner, filename, content, mime_type)
        )
        if mode == "rag" and document.mime_type not in ("text/plain", "application/pdf"):
            raise HTTPException(422, "RAG aceita textos e PDFs. Use consulta direta para imagens.")
        if chat and conversation is None:
            conversation = Conversation(
                owner_id=owner, document_id=document.id, title=question[:200]
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        version = conversation.version if conversation else 0
        history = memory(db, conversation.id) if conversation else []
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
            history,
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
                retrieval_question = question
                if history:
                    retrieval_question = (
                        "Contexto anterior: "
                        + " ".join(m["parts"][0]["text"][:800] for m in history[-4:])
                        + "\nPergunta atual: "
                        + question
                    )
                retrieved = await retrieve(db, document, retrieval_question, self.gemini)
                for source in retrieved:
                    source.document_id = str(document.id)
                    if source.section and source.section.startswith("Pagina "):
                        source.page = int(source.section.split(",")[0].split()[1])
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
            answer, model = await self.gemini.generate(prompt, payload, mime, history=history)
            usage = self.gemini.usage
            for kind, value in usage.items():
                GENERATION_TOKENS_TOTAL.labels(kind=kind).inc(value)
        if conversation:
            changed = db.execute(
                update(Conversation)
                .where(Conversation.id == conversation.id, Conversation.version == version)
                .values(version=version + 1)
            )
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(
                    409,
                    "A conversa mudou durante o envio. Reabra a conversa antes de tentar novamente.",
                )
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
            conversation_id=conversation.id if conversation else None,
            turn_number=version + 1 if conversation else None,
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
            conversation_id=str(conversation.id) if conversation else None,
            mode=mode,
            **usage,
        )

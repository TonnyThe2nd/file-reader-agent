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
from app.models.governance import DailyUsage, InteractionDocument
from app.schemas.ask import AskResponse, RetrievalFilters
from app.services.agent_service import AGENT_PROMPT_VERSION, AgentService
from app.services.conversation_service import get_conversation, memory
from app.services.document_service import INDEX_VERSION, get_document, save_document
from app.services.governance_service import audit, reserve_query
from app.services.ollama_service import OllamaService
from app.services.retrieval_service import RETRIEVAL_VERSION, filter_documents, retrieve_many

PROMPT_VERSION = "ollama-grounded-v3"


class RAGService:
    def __init__(self, ollama: OllamaService):
        self.ollama = ollama

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
        document_ids: list[UUID] | None = None,
        hybrid: bool = True,
        rerank: bool = True,
        filters: RetrievalFilters | None = None,
    ) -> AskResponse:
        start = time.perf_counter()
        if mode == "multiagent" and not self.ollama.config.multiagent_enabled:
            raise HTTPException(422, "O modo multiagente esta desabilitado.")
        conversation = get_conversation(db, conversation_id, owner) if conversation_id else None
        if conversation:
            if conversation.document_ids:
                document_ids = [UUID(value) for value in conversation.document_ids]
            if not conversation.document_id:
                raise HTTPException(
                    410, "O documento desta conversa foi excluido. Inicie outra conversa."
                )
            document_id = conversation.document_id
        if document_ids is not None:
            if not 1 <= len(document_ids) <= 20:
                raise HTTPException(422, "Selecione de 1 a 20 documentos.")
            if mode != "rag" and (len(set(document_ids)) > 1 or conversation is None):
                raise HTTPException(422, "Selecao de varios documentos exige modo RAG.")
            documents = [
                get_document(db, value, owner) for value in sorted(set(document_ids), key=str)
            ]
            document_id = documents[0].id
        document = (
            get_document(db, document_id, owner)
            if document_id
            else save_document(db, owner, filename, content, mime_type)
        )
        if document_ids is None:
            documents = [document]
        if filters:
            documents = filter_documents(documents, filters)
            document = documents[0]
        if mode == "rag" and any(
            d.mime_type not in ("text/plain", "application/pdf")
            and not (settings.ocr_enabled and d.mime_type.startswith("image/"))
            for d in documents
        ):
            raise HTTPException(422, "RAG aceita textos e PDFs.")
        if (
            mode == "rag"
            and document.mime_type not in ("text/plain", "application/pdf")
            and not settings.ocr_enabled
        ):
            raise HTTPException(422, "RAG aceita textos e PDFs. Use consulta direta para imagens.")
        if mode == "multiagent" and document.mime_type not in ("text/plain", "application/pdf"):
            raise HTTPException(
                422, "Multiagente aceita textos e PDFs. Use consulta direta para imagens."
            )
        if chat and conversation is None:
            conversation = Conversation(
                owner_id=owner,
                document_id=document.id,
                title=question[:200],
                document_ids=[str(d.id) for d in documents] if document_ids is not None else None,
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
            settings.base_url,
            settings.default_temperature,
            settings.default_max_tokens,
            settings.ollama_embedding_dimensions,
            settings.chat_model,
            settings.embedding_model_ollama,
            settings.rag_top_k,
            INDEX_VERSION,
            PROMPT_VERSION,
            history,
            [(str(d.id), d.sha256) for d in documents],
            RETRIEVAL_VERSION,
            hybrid,
            rerank,
            settings.ollama_max_context_chars,
            settings.ocr_enabled,
            settings.ocr_languages,
            settings.redact_sensitive_data,
            filters.model_dump(mode="json") if filters else None,
        ]
        if mode == "multiagent":
            config = self.ollama.config
            signature.extend(
                [
                    AGENT_PROMPT_VERSION,
                    config.multiagent_model or config.chat_model,
                    config.multiagent_max_steps,
                    config.multiagent_timeout_seconds,
                    config.ollama_max_context_chars,
                ]
            )
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
        reservation = (
            0
            if cached
            else 4 * (settings.ollama_max_context_chars + 14000) + settings.default_max_tokens
        )
        if mode == "multiagent":
            reservation *= settings.multiagent_max_steps
        if not cached and document.mime_type.startswith("image/"):
            reservation += document.size_bytes * 2
        day = reserve_query(db, owner, reservation)
        for item in documents:
            audit(db, owner, "document.query", item.id)
        db.commit()
        usage = {"input_tokens": 0, "output_tokens": 0}
        if cached:
            answer, model, sources = cached.answer, cached.model_used, cached.sources
            CACHE_HITS_TOTAL.inc()
        elif mode == "multiagent":
            agents = AgentService(self.ollama)
            answer, model, sources = await agents.ask(question, document, history, db)
            usage = agents.usage
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
                retrieved = await retrieve_many(
                    db, documents, retrieval_question, self.ollama, hybrid=hybrid, rerank=rerank
                )
                if not retrieved:
                    raise HTTPException(
                        422, "Nenhum trecho cabe no limite de contexto configurado."
                    )
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
            answer, model = await self.ollama.generate(prompt, payload, mime, history=history)
            usage = self.ollama.usage
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
        db.flush()
        for item in documents:
            db.add(InteractionDocument(interaction_id=row.id, document_id=item.id))
        db.execute(
            update(DailyUsage)
            .where(DailyUsage.owner_id == owner, DailyUsage.day == day)
            .values(tokens=DailyUsage.tokens - reservation + sum(usage.values()))
        )
        audit(db, owner, "query.complete", row.id)
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
            document_ids=[str(d.id) for d in documents],
            conversation_id=str(conversation.id) if conversation else None,
            follow_up_questions=[
                "Quais trechos sustentam esta resposta?",
                "Quais informacoes ainda faltam nos documentos?",
                "Compare as evidencias dos documentos."
                if len(documents) > 1
                else "Resuma os pontos principais em uma lista.",
            ],
            turn_number=row.turn_number,
            mode=mode,
            **usage,
        )

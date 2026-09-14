import asyncio
import json
import time
from contextlib import nullcontext, suppress
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_rag_service
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.metrics import ASK_LATENCY_SECONDS, ASK_REQUESTS_TOTAL
from app.core.security import limit_requests
from app.schemas.ask import AskMode, AskResponse, RetrievalFilters
from app.services.file_service import read_attachment
from app.services.governance_service import audit
from app.services.ollama_service import OllamaServiceError
from app.services.rag_service import RAGService

router = APIRouter(tags=["ask"])
logger = get_logger(__name__)


def record_failure(db, owner):
    with suppress(SQLAlchemyError):
        db.rollback()
        audit(db, owner, "query.error")
        db.commit()


@router.post("/ask", response_model=AskResponse)
async def ask(
    question: Annotated[str, Form(min_length=1, max_length=2000)],
    service: Annotated[RAGService, Depends(get_rag_service)],
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
    file: Annotated[UploadFile | None, File(description="Arquivo de ate 10 MiB")] = None,
    document_id: Annotated[UUID | None, Form()] = None,
    mode: Annotated[AskMode, Form()] = "direct",
    use_cache: Annotated[bool, Form()] = True,
    conversation_id: Annotated[UUID | None, Form()] = None,
    chat: Annotated[bool, Form()] = False,
    document_ids: Annotated[list[UUID] | None, Form()] = None,
    hybrid: Annotated[bool, Form()] = True,
    rerank: Annotated[bool, Form()] = True,
    stream: Annotated[bool, Form()] = False,
    filters: Annotated[str | None, Form(max_length=2000)] = None,
) -> AskResponse:
    try:
        with nullcontext() if stream else ASK_LATENCY_SECONDS.time():
            question = question.strip()
            try:
                retrieval_filters = (
                    RetrievalFilters.model_validate_json(filters) if filters else None
                )
            except ValidationError:
                raise HTTPException(
                    422, "Filtros invalidos. Envie um objeto JSON de metadados."
                ) from None
            if retrieval_filters and mode != "rag":
                raise HTTPException(422, "Filtros de recuperacao exigem modo RAG.")
            if not question:
                raise HTTPException(422, "A pergunta nao pode conter apenas espacos.")
            if (
                sum(
                    value is not None
                    for value in (file, document_id, conversation_id, document_ids)
                )
                != 1
            ):
                raise HTTPException(
                    422,
                    "Envie exatamente um arquivo, document_id, document_ids ou conversation_id.",
                )
            content, mime_type = (
                await read_attachment(file, settings.max_upload_bytes) if file else (None, None)
            )
            if stream and mode == "multiagent":
                raise HTTPException(422, "Streaming disponivel nos modos direto e RAG.")

            async def run():
                return await service.ask(
                    question,
                    db,
                    owner,
                    content=content,
                    mime_type=mime_type,
                    filename=Path((file.filename or "documento").replace("\\", "/")).name
                    if file
                    else "documento",
                    document_id=document_id,
                    mode=mode,
                    use_cache=use_cache,
                    conversation_id=conversation_id,
                    chat=chat,
                    document_ids=document_ids,
                    hybrid=hybrid,
                    rerank=rerank,
                    filters=retrieval_filters,
                )

            if stream:

                async def events():
                    started = time.perf_counter()
                    queue = asyncio.Queue(maxsize=128)

                    async def token(value):
                        await queue.put(("token", {"text": value}))

                    async def produce():
                        service.ollama.on_token = token
                        try:
                            response = await run()
                            await queue.put(("done", response.model_dump(mode="json")))
                            ASK_REQUESTS_TOTAL.labels(status="success").inc()
                        except Exception as exc:
                            record_failure(db, owner)
                            ASK_REQUESTS_TOTAL.labels(status="error").inc()
                            await queue.put(
                                (
                                    "error",
                                    {
                                        "detail": exc.detail
                                        if isinstance(exc, (HTTPException, OllamaServiceError))
                                        else "Falha ao concluir resposta.",
                                        "status": getattr(exc, "status_code", 500),
                                    },
                                )
                            )

                    task = asyncio.create_task(produce())
                    try:
                        while True:
                            try:
                                kind, payload = await asyncio.wait_for(queue.get(), 15)
                            except asyncio.TimeoutError:
                                yield ": heartbeat\n\n"
                                continue
                            yield f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                            if kind in ("done", "error"):
                                break
                    finally:
                        ASK_LATENCY_SECONDS.observe(time.perf_counter() - started)
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task

                return StreamingResponse(
                    events(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
                )
            response = await run()
        ASK_REQUESTS_TOTAL.labels(status="success").inc()
        return response
    except OllamaServiceError as exc:
        record_failure(db, owner)
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        raise HTTPException(exc.status_code, exc.detail) from None
    except HTTPException:
        record_failure(db, owner)
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        raise
    except SQLAlchemyError:
        record_failure(db, owner)
        db.rollback()
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        raise
    except Exception:
        record_failure(db, owner)
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        logger.error("Erro interno no /ask")
        raise HTTPException(500, "Erro interno ao processar a pergunta.") from None
    finally:
        if file:
            await file.close()

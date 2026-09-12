from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_rag_service
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.metrics import ASK_LATENCY_SECONDS, ASK_REQUESTS_TOTAL
from app.core.security import limit_requests
from app.schemas.ask import AskResponse
from app.services.file_service import read_attachment
from app.services.ollama_service import OllamaServiceError
from app.services.rag_service import RAGService

router = APIRouter(tags=["ask"])
logger = get_logger(__name__)


@router.post("/ask", response_model=AskResponse)
async def ask(
    question: Annotated[str, Form(min_length=1, max_length=2000)],
    service: Annotated[RAGService, Depends(get_rag_service)],
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
    file: Annotated[UploadFile | None, File(description="Arquivo de ate 10 MiB")] = None,
    document_id: Annotated[UUID | None, Form()] = None,
    mode: Annotated[Literal["direct", "rag"], Form()] = "direct",
    use_cache: Annotated[bool, Form()] = True,
    conversation_id: Annotated[UUID | None, Form()] = None,
    chat: Annotated[bool, Form()] = False,
) -> AskResponse:
    try:
        with ASK_LATENCY_SECONDS.time():
            question = question.strip()
            if not question:
                raise HTTPException(422, "A pergunta nao pode conter apenas espacos.")
            if sum(value is not None for value in (file, document_id, conversation_id)) != 1:
                raise HTTPException(
                    422, "Envie exatamente um arquivo, document_id ou conversation_id."
                )
            content, mime_type = (
                await read_attachment(file, settings.max_upload_bytes) if file else (None, None)
            )
            response = await service.ask(
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
            )
        ASK_REQUESTS_TOTAL.labels(status="success").inc()
        return response
    except OllamaServiceError as exc:
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        raise HTTPException(exc.status_code, exc.detail) from None
    except HTTPException:
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        raise
    except SQLAlchemyError:
        db.rollback()
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        raise
    except Exception:
        ASK_REQUESTS_TOTAL.labels(status="error").inc()
        logger.error("Erro interno no /ask")
        raise HTTPException(500, "Erro interno ao processar a pergunta.") from None
    finally:
        if file:
            await file.close()

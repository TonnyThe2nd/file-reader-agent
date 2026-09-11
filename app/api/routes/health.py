from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import current_owner
from app.models import Conversation, Document, DocumentChunk, Feedback, Interaction

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Annotated[Session, Depends(get_db)], owner: Annotated[str, Depends(current_owner)]):
    try:
        for model in (Conversation, Document, DocumentChunk, Feedback, Interaction):
            db.execute(select(model).limit(0))
    except SQLAlchemyError:
        raise HTTPException(503, "Banco indisponivel ou migrations pendentes.") from None
    return {
        "status": "ok",
        "database": "ok",
        "gemini_configured": bool(settings.gemini_api_key.get_secret_value().strip()),
        "owner": owner,
    }


@router.get("/config")
def public_config():
    return {
        "auth_required": bool(settings.api_tokens) or settings.app_env != "development",
        "max_upload_bytes": settings.max_upload_bytes,
    }

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import current_owner, limit_requests
from app.models import Document
from app.schemas.document import DocumentSummary
from app.services.document_service import get_document, save_document
from app.services.file_service import read_attachment

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=list[DocumentSummary])
def documents(
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return list(
        db.scalars(
            select(Document)
            .where(Document.owner_id == owner)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/documents", response_model=DocumentSummary)
async def upload(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
):
    try:
        content, mime_type = await read_attachment(file, settings.max_upload_bytes)
        name = Path((file.filename or "documento").replace("\\", "/")).name
        return DocumentSummary.model_validate(save_document(db, owner, name, content, mime_type))
    finally:
        await file.close()


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
):
    db.delete(get_document(db, document_id, owner))
    db.commit()
    return Response(status_code=204)

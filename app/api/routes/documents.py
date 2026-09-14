from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import current_owner, limit_requests
from app.models import Document
from app.schemas.document import DocumentSummary
from app.services.document_service import get_document, save_document
from app.services.file_service import read_attachment
from app.services.governance_service import accessible_documents, audit

router = APIRouter(tags=["documents"])


@router.get("/documents/{document_id}/content")
def document_content(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
):
    document = get_document(db, document_id, owner)
    audit(db, owner, "document.read", document_id)
    db.commit()
    return Response(
        document.content,
        media_type=document.mime_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.get("/documents/{document_id}", response_model=DocumentSummary)
def document_metadata(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
):
    return get_document(db, document_id, owner)


@router.get("/documents", response_model=list[DocumentSummary])
def documents(
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str, Query(max_length=255)] = "",
    category: Annotated[str | None, Query(max_length=100)] = None,
    mime_type: Annotated[str | None, Query(max_length=100)] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
):
    if created_from and created_from.tzinfo is None:
        created_from = created_from.replace(tzinfo=timezone.utc)
    if created_to and created_to.tzinfo is None:
        created_to = created_to.replace(tzinfo=timezone.utc)
    if created_from and created_to and created_from > created_to:
        raise HTTPException(422, "Intervalo de datas invalido.")
    query = select(Document).where(accessible_documents(db, owner))
    if search:
        query = query.where(Document.name.icontains(search, autoescape=True))
    if category is not None:
        query = query.where(Document.category == category)
    if mime_type is not None:
        query = query.where(Document.mime_type == mime_type)
    if created_from:
        query = query.where(Document.created_at >= created_from)
    if created_to:
        query = query.where(Document.created_at <= created_to)
    rows = list(
        db.scalars(
            query.order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return [
        DocumentSummary.model_validate(row).model_copy(update={"can_manage": row.owner_id == owner})
        for row in rows
    ]


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
    purge_history: bool = False,
):
    row = get_document(db, document_id, owner, write=True)
    if purge_history:
        from app.services.retention_service import purge_document_history

        purge_document_history(db, document_id)
    db.delete(row)
    audit(db, owner, "document.delete", document_id)
    db.commit()
    return Response(status_code=204)


class DocumentMetadata(BaseModel):
    category: str | None = Field(default=None, max_length=100)


@router.patch("/documents/{document_id}", response_model=DocumentSummary)
def update_metadata(
    document_id: UUID,
    body: DocumentMetadata,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
):
    row = get_document(db, document_id, owner, write=True)
    row.category = body.category
    audit(db, owner, "document.metadata", document_id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/documents/{document_id}/retry", response_model=DocumentSummary)
def retry_processing(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
):
    row = get_document(db, document_id, owner, write=True)
    if row.processing_status != "failed":
        raise HTTPException(409, "Somente documentos com falha podem ser reenfileirados.")
    row.processing_status = "pending"
    row.processing_attempts = 0
    row.processing_progress = 0
    row.processing_error = None
    row.processing_available_at = None
    row.processing_token = None
    db.commit()
    db.refresh(row)
    return row

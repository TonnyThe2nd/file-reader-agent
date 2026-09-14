from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_owner
from app.models.conversation import Conversation
from app.services.conversation_service import conversation_messages, get_conversation
from app.services.document_service import get_document

router = APIRouter(tags=["conversations"])


@router.get("/conversations")
def conversations(
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return [
        {
            "id": row.id,
            "title": row.title,
            "document_id": row.document_id,
            "created_at": row.created_at,
            "parent_conversation_id": row.parent_conversation_id,
            "parent_turn": row.parent_turn,
        }
        for row in db.scalars(
            select(Conversation)
            .where(Conversation.owner_id == owner)
            .order_by(Conversation.created_at.desc(), Conversation.id.desc())
            .offset(offset)
            .limit(20)
        )
    ]


@router.get("/conversations/{conversation_id}")
def conversation(
    conversation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
    before: Annotated[int | None, Query(ge=1)] = None,
):
    row = get_conversation(db, conversation_id, owner)
    messages = conversation_messages(db, row, before)
    return {
        "id": row.id,
        "title": row.title,
        "parent_conversation_id": row.parent_conversation_id,
        "parent_turn": row.parent_turn,
        "document_id": row.document_id,
        "document_ids": row.document_ids or ([str(row.document_id)] if row.document_id else []),
        "messages": [
            {
                "interaction_id": m.id,
                "question": m.question,
                "answer": m.answer,
                "sources": m.sources,
                "document_id": m.document_id,
                "conversation_id": row.id,
                "turn_number": m.turn_number,
                "mode": m.mode,
                "model_used": m.model_used,
                "latency_ms": m.latency_ms,
                "cache_hit": m.cache_hit,
                "rating": m.feedback.rating if m.feedback else None,
            }
            for m in reversed(messages)
        ],
        "next_before": messages[-1].turn_number if len(messages) == 50 else None,
    }


class BranchRequest(BaseModel):
    turn: int = Field(ge=0)
    title: str = Field(default="Nova ramificacao", min_length=1, max_length=200)
    document_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=20)


@router.post("/conversations/{conversation_id}/branches", status_code=201)
def branch(
    conversation_id: UUID,
    body: BranchRequest,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
):
    parent = get_conversation(db, conversation_id, owner)
    if body.turn > parent.version:
        raise HTTPException(422, "Turno inexistente.")
    # Check depth even for an empty branch to prevent unreadable chains.
    ancestor, depth = parent, 1
    while ancestor.parent_conversation_id:
        depth += 1
        if depth >= 20:
            raise HTTPException(422, "Limite de ramificacoes atingido.")
        ancestor = get_conversation(db, ancestor.parent_conversation_id, owner)
    ids = body.document_ids or [
        UUID(value)
        for value in (
            parent.document_ids or ([str(parent.document_id)] if parent.document_id else [])
        )
    ]
    if not ids:
        raise HTTPException(410, "Documento excluido.")
    for value in ids:
        get_document(db, value, owner)
    row = Conversation(
        owner_id=owner,
        document_id=ids[0],
        document_ids=[str(value) for value in ids]
        if len(ids) > 1 or body.document_ids
        else parent.document_ids,
        title=body.title,
        version=body.turn,
        parent_conversation_id=parent.id,
        parent_turn=body.turn,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "parent_conversation_id": parent.id, "parent_turn": body.turn}

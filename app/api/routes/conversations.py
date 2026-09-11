from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_owner
from app.models.conversation import Conversation
from app.models.interaction import Interaction
from app.services.conversation_service import get_conversation

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
    query = select(Interaction).where(
        Interaction.conversation_id == row.id, Interaction.owner_id == owner
    )
    if before is not None:
        query = query.where(Interaction.turn_number < before)
    messages = list(db.scalars(query.order_by(Interaction.turn_number.desc()).limit(50)))
    return {
        "id": row.id,
        "title": row.title,
        "document_id": row.document_id,
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

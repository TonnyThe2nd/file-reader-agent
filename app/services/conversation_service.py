from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.interaction import Interaction


def get_conversation(db: Session, conversation_id: UUID, owner: str) -> Conversation:
    row = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.owner_id == owner
        )
    )
    if row is None:
        raise HTTPException(404, "Conversa nao encontrada.")
    return row


def memory(db: Session, conversation_id: UUID) -> list[dict]:
    rows = list(
        db.scalars(
            select(Interaction)
            .where(Interaction.conversation_id == conversation_id)
            .order_by(Interaction.turn_number.desc())
            .limit(6)
        )
    )
    history = []
    remaining = 12000
    pairs = []
    for row in rows:
        question, answer = row.question, row.answer[:3000]
        if len(question) + len(answer) > remaining:
            break
        pairs.append((question, answer))
        remaining -= len(question) + len(answer)
    for question, answer in reversed(pairs):
        history.extend(
            [
                {"role": "user", "parts": [{"text": question}]},
                {"role": "model", "parts": [{"text": answer}]},
            ]
        )
    return history

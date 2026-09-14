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


def conversation_messages(db: Session, row: Conversation, before=None, limit=50):
    rows = []
    visited = set()
    while row and len(rows) < limit:
        if row.id in visited or len(visited) >= 20:
            raise HTTPException(422, "Limite de profundidade da conversa atingido.")
        visited.add(row.id)
        query = select(Interaction).where(
            Interaction.conversation_id == row.id, Interaction.owner_id == row.owner_id
        )
        if before is not None:
            query = query.where(Interaction.turn_number < before)
        rows.extend(
            db.scalars(query.order_by(Interaction.turn_number.desc()).limit(limit - len(rows)))
        )
        if not row.parent_conversation_id:
            break
        before = min(before, row.parent_turn + 1) if before is not None else row.parent_turn + 1
        row = get_conversation(db, row.parent_conversation_id, row.owner_id)
    return rows


def memory(db: Session, conversation_id: UUID) -> list[dict]:
    from app.services.document_service import get_document

    rows = conversation_messages(db, db.get(Conversation, conversation_id), limit=6)
    history = []
    remaining = 12000
    pairs = []
    for row in rows:
        if row.document_id is None:
            raise HTTPException(
                410, "O contexto inclui um documento excluido. Inicie outra conversa."
            )
        ids = {row.document_id}
        ids.update(
            UUID(source["document_id"]) for source in row.sources if source.get("document_id")
        )
        for document_id in ids:
            get_document(db, document_id, row.owner_id)
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

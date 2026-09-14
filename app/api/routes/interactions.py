from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_owner
from app.models import Interaction
from app.schemas.ask import AskMode
from app.schemas.interaction import InteractionDetail, InteractionSummary
from app.services.governance_service import audit
from app.services.history_service import list_interactions

router = APIRouter(tags=["interactions"])


@router.get("/interactions", response_model=list[InteractionSummary])
def interactions(
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str, Query(max_length=200)] = "",
    mode: AskMode | None = None,
    document_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[InteractionSummary]:
    if created_from and created_from.tzinfo is None:
        created_from = created_from.replace(tzinfo=timezone.utc)
    if created_to and created_to.tzinfo is None:
        created_to = created_to.replace(tzinfo=timezone.utc)
    if created_from and created_to and created_from > created_to:
        raise HTTPException(422, "Intervalo de datas invalido.")
    return list_interactions(
        db,
        limit,
        offset,
        owner,
        search,
        mode=mode,
        document_id=document_id,
        created_from=created_from,
        created_to=created_to,
    )


def find_interaction(db: Session, interaction_id: UUID, owner: str) -> Interaction:
    row = db.scalar(
        select(Interaction).where(Interaction.id == interaction_id, Interaction.owner_id == owner)
    )
    if row is None:
        raise HTTPException(404, "Interaçao nao encontrada.")
    return row


@router.get("/interactions/{interaction_id}", response_model=InteractionDetail)
def detail(
    interaction_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
):
    row = find_interaction(db, interaction_id, owner)
    audit(db, owner, "query.read", interaction_id)
    db.commit()
    values = {
        field: getattr(row, field)
        for field in InteractionDetail.model_fields
        if field not in ("rating", "comment")
    }
    return InteractionDetail(
        **values,
        rating=row.feedback.rating if row.feedback else None,
        comment=row.feedback.comment if row.feedback else None,
    )


@router.delete("/interactions/{interaction_id}", status_code=204)
def delete_interaction(
    interaction_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
):
    db.delete(find_interaction(db, interaction_id, owner))
    audit(db, owner, "query.delete", interaction_id)
    db.commit()
    return Response(status_code=204)

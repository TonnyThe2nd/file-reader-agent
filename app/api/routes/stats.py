from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_owner
from app.schemas.stats import StatsResponse
from app.services.history_service import get_stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def stats(
    db: Annotated[Session, Depends(get_db)], owner: Annotated[str, Depends(current_owner)]
) -> StatsResponse:
    return get_stats(db, owner)

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.metrics import FEEDBACK_TOTAL
from app.core.security import current_owner
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.feedback_service import DuplicateFeedbackError, feedback_service

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(
    request: FeedbackRequest,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
) -> FeedbackResponse:
    try:
        feedback_service.save(request, db, owner)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
    except DuplicateFeedbackError as exc:
        raise HTTPException(409, str(exc)) from None
    FEEDBACK_TOTAL.labels(rating=str(request.rating)).inc()
    return FeedbackResponse(status="ok", message="Feedback registrado com sucesso.")

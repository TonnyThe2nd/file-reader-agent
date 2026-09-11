from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Feedback, Interaction
from app.schemas.feedback import FeedbackRequest

logger = get_logger(__name__)


class DuplicateFeedbackError(Exception):
    pass


class FeedbackService:
    def save(self, feedback: FeedbackRequest, db: Session, owner: str = "local") -> None:
        interaction = db.get(Interaction, feedback.interaction_id)
        if interaction is None or interaction.owner_id != owner:
            logger.info("Feedback recusado: interacao inexistente | id=%s", feedback.interaction_id)
            raise ValueError("Interacao nao encontrada.")
        if db.scalar(select(Feedback.id).where(Feedback.interaction_id == feedback.interaction_id)):
            raise DuplicateFeedbackError("Esta interacao ja possui feedback.")
        fb = Feedback(**feedback.model_dump())
        try:
            db.add(fb)
            db.commit()
        except IntegrityError:
            db.rollback()
            if db.get(Interaction, feedback.interaction_id) is None:
                raise ValueError("Interacao nao encontrada.") from None
            if db.scalar(
                select(Feedback.id).where(Feedback.interaction_id == feedback.interaction_id)
            ):
                raise DuplicateFeedbackError("Esta interacao ja possui feedback.") from None
            raise
        except SQLAlchemyError:
            db.rollback()
            raise
        logger.info(
            "Feedback salvo | interaction_id=%s rating=%s", feedback.interaction_id, feedback.rating
        )


feedback_service = FeedbackService()

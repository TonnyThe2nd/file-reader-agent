from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select, true
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Feedback, Interaction
from app.schemas.interaction import InteractionSummary
from app.schemas.stats import StatsResponse

logger = get_logger(__name__)


def list_interactions(
    db: Session, limit: int, offset: int, owner: str = "local", search: str = ""
) -> list[InteractionSummary]:
    rows = (
        db.execute(
            select(
                Interaction.id,
                Interaction.question,
                func.substr(Interaction.answer, 1, 200).label("answer"),
                Interaction.latency_ms,
                Interaction.model_used,
                Interaction.created_at,
                Feedback.rating,
            )
            .outerjoin(Feedback, Feedback.interaction_id == Interaction.id)
            .where(
                Interaction.owner_id == owner,
                Interaction.question.icontains(search, autoescape=True),
            )
            .order_by(Interaction.created_at.desc(), Interaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .mappings()
        .all()
    )
    logger.info("Historico consultado | limit=%s offset=%s count=%s", limit, offset, len(rows))
    return [InteractionSummary.model_validate(row) for row in rows]


def get_stats(db: Session, owner: str = "local") -> StatsResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    interactions = (
        select(
            func.count(Interaction.id).label("total_interactions"),
            func.coalesce(func.avg(Interaction.latency_ms), 0.0).label("avg_latency_ms"),
            func.coalesce(
                func.avg(case((Interaction.created_at >= cutoff, Interaction.latency_ms))), 0.0
            ).label("avg_latency_ms_last_24h"),
        )
        .where(Interaction.owner_id == owner)
        .subquery()
    )
    feedbacks = (
        select(
            func.count(Feedback.id).label("total_feedbacks"),
            func.count(case((Feedback.rating == 1, 1))).label("positive_feedbacks"),
            func.count(case((Feedback.rating == -1, 1))).label("negative_feedbacks"),
        )
        .join(Interaction, Interaction.id == Feedback.interaction_id)
        .where(Interaction.owner_id == owner)
        .subquery()
    )
    row = (
        db.execute(select(interactions, feedbacks).join(feedbacks, onclause=true()))
        .mappings()
        .one()
    )
    values = dict(row)
    values["positive_rate"] = (
        100.0 * values["positive_feedbacks"] / values["total_feedbacks"]
        if values["total_feedbacks"]
        else 0.0
    )
    logger.info("Estatisticas consultadas")
    return StatsResponse(**values)

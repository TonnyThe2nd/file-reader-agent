import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import current_owner
from app.models import Document, Interaction
from app.models.governance import AuditEvent, DailyUsage, InteractionDocument, UserPolicy
from app.services.governance_service import accessible_documents, policy

router = APIRouter(tags=["analytics"])


@router.get("/analytics")
def analytics(
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
    team: Annotated[str | None, Query(max_length=100)] = None,
):
    owners = [owner]
    if team:
        rule = policy(db, owner)
        if rule.role not in ("admin", "manager") or team not in rule.teams:
            raise HTTPException(403, "Sem permissao para metricas desta equipe.")
        owners = [row.owner_id for row in db.scalars(select(UserPolicy)) if team in row.teams]
    rows = list(
        db.scalars(
            select(Interaction)
            .where(Interaction.owner_id.in_(owners))
            .order_by(Interaction.created_at.desc())
            .limit(1000)
        )
    )
    latencies = sorted(row.latency_ms for row in rows)
    tokens = db.scalar(
        select(
            func.coalesce(func.sum(Interaction.input_tokens + Interaction.output_tokens), 0)
        ).where(Interaction.owner_id.in_(owners))
    )
    cited, eligible = 0, 0
    for row in rows:
        if row.mode == "rag":
            eligible += 1
            references = [int(value) for value in re.findall(r"\[(\d+)\]", row.answer)]
            cited += bool(references) and all(
                1 <= value <= len(row.sources) for value in references
            )
    documents = db.execute(
        select(Document.id, Document.name, func.count(Interaction.id))
        .join(InteractionDocument, InteractionDocument.document_id == Document.id)
        .join(Interaction, Interaction.id == InteractionDocument.interaction_id)
        .where(Interaction.owner_id.in_(owners), accessible_documents(db, owner))
        .group_by(Document.id, Document.name)
        .order_by(func.count(Interaction.id).desc())
        .limit(100)
    ).all()
    statuses = db.execute(
        select(Document.processing_status, func.count())
        .where(accessible_documents(db, owner))
        .group_by(Document.processing_status)
    ).all()
    usage = db.get(DailyUsage, (owner, datetime.now(timezone.utc).date().isoformat()))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    outcomes = dict(
        db.execute(
            select(AuditEvent.action, func.count())
            .where(
                AuditEvent.owner_id.in_(owners),
                AuditEvent.created_at >= cutoff,
                AuditEvent.action.in_(["query.error", "query.complete"]),
            )
            .group_by(AuditEvent.action)
        ).all()
    )
    failures = outcomes.get("query.error", 0)
    completed = outcomes.get("query.complete", 0)
    return {
        "errors_last_24h": failures,
        "error_rate_last_24h": failures / max(1, failures + completed) * 100,
        "scope": team or owner,
        "sample_size": len(rows),
        "total_tokens": tokens,
        "estimated_cost": tokens / 1000000 * settings.estimated_cost_per_million_tokens,
        "p95_latency_ms": latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)]
        if latencies
        else 0,
        "citation_validity_rate": cited / eligible * 100 if eligible else 0,
        "processing": dict(statuses),
        "documents": [{"id": row[0], "name": row[1], "queries": row[2]} for row in documents],
        "daily_queries": usage.queries if usage else 0,
        "daily_reserved_tokens": usage.tokens if usage else 0,
    }

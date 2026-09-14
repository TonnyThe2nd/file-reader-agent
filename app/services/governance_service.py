from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models import Document
from app.models.governance import AuditEvent, DailyUsage, DocumentGrant, UserPolicy


def policy(db, owner):
    row = db.get(UserPolicy, owner)
    if row is not None and owner in settings.admin_owners:
        return UserPolicy(
            owner_id=owner,
            role="admin",
            teams=list(row.teams),
            daily_queries=row.daily_queries,
            daily_tokens=row.daily_tokens,
            storage_bytes=row.storage_bytes,
            retention_days=row.retention_days,
        )
    return row or UserPolicy(
        owner_id=owner,
        role="admin" if owner in settings.admin_owners else "user",
        teams=[],
        daily_queries=1000,
        daily_tokens=10000000,
        storage_bytes=104857600,
    )


def require_admin(db, owner):
    if policy(db, owner).role != "admin":
        raise HTTPException(403, "Acesso restrito a administradores.")


def ensure_policy(db, owner):
    if db.get(UserPolicy, owner) is None:
        try:
            with db.begin_nested():
                db.add(policy(db, owner))
                db.flush()
        except IntegrityError:
            pass


def accessible_documents(db, owner):
    teams = policy(db, owner).teams
    grants = select(DocumentGrant.document_id).where(
        or_(
            and_(DocumentGrant.kind == "user", DocumentGrant.recipient == owner),
            and_(DocumentGrant.kind == "team", DocumentGrant.recipient.in_(teams)),
        )
    )
    return or_(Document.owner_id == owner, Document.id.in_(grants))


def audit(db, owner, action, resource_id=None):
    db.add(
        AuditEvent(
            owner_id=owner, action=action, resource_id=str(resource_id) if resource_id else None
        )
    )


def reserve_query(db, owner, tokens):
    """Atomic daily reservation avoids quota overshoot across concurrent API processes."""
    limits = policy(db, owner)
    day = datetime.now(timezone.utc).date().isoformat()
    key = {"owner_id": owner, "day": day}
    if db.get(DailyUsage, (owner, day)) is None:
        try:
            with db.begin_nested():
                db.add(DailyUsage(**key, queries=0, tokens=0))
                db.flush()
        except IntegrityError:
            pass
    result = db.execute(
        update(DailyUsage)
        .where(
            DailyUsage.owner_id == owner,
            DailyUsage.day == day,
            DailyUsage.queries < limits.daily_queries,
            DailyUsage.tokens <= limits.daily_tokens - tokens,
        )
        .values(queries=DailyUsage.queries + 1, tokens=DailyUsage.tokens + tokens)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(429, "Limite diario de consultas ou tokens atingido.")
    db.commit()
    return day

"""Purge expired data in bounded batches; policies are disabled by default."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.models import Conversation, Document, Interaction
from app.models.governance import InteractionDocument, UserPolicy
from app.services.governance_service import audit


def purge_document_history(db, document_id):
    ids = select(InteractionDocument.interaction_id).where(
        InteractionDocument.document_id == document_id
    )
    db.execute(
        delete(Interaction)
        .where(Interaction.id.in_(ids))
        .execution_options(synchronize_session=False)
    )


def apply_retention(db, *, dry_run=True):
    counts = {"documents": 0, "interactions": 0, "conversations": 0}
    for rule in db.scalars(select(UserPolicy).where(UserPolicy.retention_days.is_not(None))):
        cutoff = datetime.now(timezone.utc) - timedelta(days=rule.retention_days)
        for model, label in (
            (Document, "documents"),
            (Interaction, "interactions"),
            (Conversation, "conversations"),
        ):
            rows = list(
                db.scalars(
                    select(model)
                    .where(model.owner_id == rule.owner_id, model.created_at < cutoff)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            )
            counts[label] += len(rows)
            if not dry_run:
                for row in rows:
                    if model is Document:
                        purge_document_history(db, row.id)
                    audit(db, "system", "retention." + label, row.id)
                    db.delete(row)
                db.flush()
    if not dry_run:
        db.commit()
    return counts

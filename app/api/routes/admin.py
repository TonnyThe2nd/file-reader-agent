from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import current_owner, limit_requests
from app.models.governance import AuditEvent, DocumentGrant, UserPolicy
from app.services.document_service import get_document
from app.services.governance_service import audit, policy, require_admin

router = APIRouter(tags=["administration"])


class PolicyInput(BaseModel):
    role: Literal["admin", "user", "manager"] = "user"
    teams: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=30
    )
    daily_queries: int = Field(default=1000, ge=0, le=1000000)
    daily_tokens: int = Field(default=10000000, ge=0, le=2000000000)
    storage_bytes: int = Field(default=104857600, ge=0, le=2000000000)
    retention_days: int | None = Field(default=None, ge=1, le=3650)


@router.get("/me")
def me(db: Annotated[Session, Depends(get_db)], owner: Annotated[str, Depends(current_owner)]):
    row = policy(db, owner)
    return {"owner": owner, **{name: getattr(row, name) for name in PolicyInput.model_fields}}


@router.get("/admin/users")
def users(db: Annotated[Session, Depends(get_db)], owner: Annotated[str, Depends(current_owner)]):
    require_admin(db, owner)
    return [
        {
            "owner": value,
            **{name: getattr(policy(db, value), name) for name in PolicyInput.model_fields},
        }
        for value in settings.api_tokens or {"local": None}
    ]


@router.put("/admin/users/{user_id}")
def update_policy(
    user_id: str,
    body: PolicyInput,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
):
    require_admin(db, owner)
    if user_id not in settings.api_tokens and not (
        user_id == "local" and settings.app_env == "development"
    ):
        raise HTTPException(404, "Usuario nao configurado.")
    if user_id == owner and body.role != "admin":
        raise HTTPException(409, "Nao remova seu proprio acesso administrativo.")
    row = db.get(UserPolicy, user_id) or UserPolicy(owner_id=user_id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    audit(db, owner, "policy.update", user_id)
    db.commit()
    return {"owner": user_id, **body.model_dump()}


class GrantInput(BaseModel):
    kind: Literal["user", "team"]
    recipient: str = Field(min_length=1, max_length=100)


def can_share(db, document_id, owner):
    get_document(db, document_id, owner, write=True)
    if policy(db, owner).role not in ("admin", "manager"):
        raise HTTPException(403, "Compartilhamento exige perfil gestor ou administrador.")


@router.get("/documents/{document_id}/grants")
def grants(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
):
    can_share(db, document_id, owner)
    return [
        {"id": row.id, "kind": row.kind, "recipient": row.recipient}
        for row in db.scalars(select(DocumentGrant).where(DocumentGrant.document_id == document_id))
    ]


@router.post("/documents/{document_id}/grants", status_code=201)
def share(
    document_id: UUID,
    body: GrantInput,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
):
    can_share(db, document_id, owner)
    if body.kind == "user" and body.recipient not in settings.api_tokens:
        raise HTTPException(404, "Usuario nao configurado.")
    if body.kind == "team" and body.recipient not in policy(db, owner).teams:
        raise HTTPException(403, "Compartilhe somente com suas equipes.")
    row = db.scalar(
        select(DocumentGrant).where(
            DocumentGrant.document_id == document_id,
            DocumentGrant.kind == body.kind,
            DocumentGrant.recipient == body.recipient,
        )
    )
    if row is None:
        row = DocumentGrant(document_id=document_id, **body.model_dump())
        db.add(row)
    audit(db, owner, "document.share", document_id)
    db.commit()
    return {"id": row.id, **body.model_dump()}


@router.delete("/documents/{document_id}/grants/{grant_id}", status_code=204)
def revoke(
    document_id: UUID,
    grant_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(limit_requests)],
):
    can_share(db, document_id, owner)
    row = db.scalar(
        select(DocumentGrant).where(
            DocumentGrant.id == grant_id, DocumentGrant.document_id == document_id
        )
    )
    if row is None:
        raise HTTPException(404, "Permissao nao encontrada.")
    db.delete(row)
    audit(db, owner, "document.revoke", document_id)
    db.commit()
    return Response(status_code=204)


@router.get("/audit")
def audit_events(
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[str, Depends(current_owner)],
    offset: Annotated[int, Query(ge=0)] = 0,
):
    query = select(AuditEvent)
    if policy(db, owner).role != "admin":
        query = query.where(AuditEvent.owner_id == owner)
    return [
        {
            "id": row.id,
            "owner": row.owner_id,
            "action": row.action,
            "resource_id": row.resource_id,
            "created_at": row.created_at,
        }
        for row in db.scalars(
            query.order_by(AuditEvent.created_at.desc(), AuditEvent.id).offset(offset).limit(100)
        )
    ]

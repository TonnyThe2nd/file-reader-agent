from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserPolicy(Base):
    __tablename__ = "user_policies"
    owner_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="user")
    teams: Mapped[list] = mapped_column(JSON, default=list)
    daily_queries: Mapped[int] = mapped_column(Integer, default=1000)
    daily_tokens: Mapped[int] = mapped_column(Integer, default=10000000)
    storage_bytes: Mapped[int] = mapped_column(Integer, default=104857600)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DocumentGrant(Base):
    __tablename__ = "document_grants"
    __table_args__ = (
        UniqueConstraint("document_id", "kind", "recipient", name="uq_document_grant"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))
    recipient: Mapped[str] = mapped_column(String(100))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class InteractionDocument(Base):
    __tablename__ = "interaction_documents"
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("interactions.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    owner_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    queries: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)

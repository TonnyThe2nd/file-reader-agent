from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(
        String(100), default="local", server_default="local", index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    cache_key: Mapped[str | None] = mapped_column(String(64), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    turn_number: Mapped[int | None] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(10), default="direct", server_default="direct")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=list)
    latency_ms: Mapped[float] = mapped_column(Float)
    model_used: Mapped[str] = mapped_column(String(100))
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="interaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

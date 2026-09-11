from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.interaction import Interaction


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("interactions.id", ondelete="CASCADE"), unique=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    interaction: Mapped["Interaction"] = relationship(back_populates="feedback")

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InteractionSummary(BaseModel):
    id: UUID
    question: str
    answer: str
    latency_ms: float
    model_used: str
    created_at: datetime
    rating: int | None = None


class InteractionDetail(InteractionSummary):
    sources: list[dict]
    cache_hit: bool
    document_id: UUID | None = None
    mode: str
    input_tokens: int
    output_tokens: int
    comment: str | None = None

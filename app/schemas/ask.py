from datetime import datetime

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    filters: dict | None = Field(default=None)


class Source(BaseModel):
    content: str
    source: str
    section: str | None = None
    score: float | None = None


class AskResponse(BaseModel):
    interaction_id: str
    answer: str
    sources: list[Source]
    latency_ms: float
    model_used: str
    cache_hit: bool
    created_at: datetime | None = None
    document_id: str | None = None
    mode: str = "direct"
    input_tokens: int = 0
    output_tokens: int = 0

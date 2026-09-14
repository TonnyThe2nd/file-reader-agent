from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AskMode = Literal["direct", "rag", "multiagent"]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: AskMode = "direct"
    filters: dict | None = Field(default=None)


class Source(BaseModel):
    content: str
    source: str
    section: str | None = None
    score: float | None = None
    document_id: str | None = None
    page: int | None = None


class AskResponse(BaseModel):
    interaction_id: str
    answer: str
    sources: list[Source]
    latency_ms: float
    model_used: str
    cache_hit: bool
    created_at: datetime | None = None
    document_id: str | None = None
    mode: AskMode = "direct"
    input_tokens: int = 0
    output_tokens: int = 0
    conversation_id: str | None = None

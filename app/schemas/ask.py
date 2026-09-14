from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AskMode = Literal["direct", "rag", "multiagent"]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: AskMode = "direct"
    filters: dict | None = Field(default=None)


class RetrievalFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str | None = Field(default=None, max_length=100)
    mime_type: str | None = Field(default=None, max_length=100)
    created_from: datetime | None = None
    created_to: datetime | None = None


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
    document_ids: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    conversation_id: str | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    turn_number: int | None = None

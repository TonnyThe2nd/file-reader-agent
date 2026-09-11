from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    interaction_id: UUID = Field(..., description="ID da interação retornado pelo /ask")
    rating: Literal[-1, 1] = Field(..., description="1 = 👍, -1 = 👎")
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    status: str
    message: str

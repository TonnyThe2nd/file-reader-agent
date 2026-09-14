from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    category: str | None = None
    processing_status: str = "pending"
    processing_progress: int = 0
    processing_attempts: int = 0
    processing_error: str | None = None
    can_manage: bool = False

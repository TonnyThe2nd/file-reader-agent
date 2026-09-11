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

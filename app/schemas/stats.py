from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_interactions: int
    total_feedbacks: int
    positive_feedbacks: int
    negative_feedbacks: int
    positive_rate: float
    avg_latency_ms: float
    avg_latency_ms_last_24h: float

from pydantic import BaseModel, Field
from typing import Any


class CacheSetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    value: Any
    ttl: int = Field(default=300, ge=1, le=86400)   # 1s – 24h


class CacheStats(BaseModel):
    hits: int
    misses: int
    total: int
    hit_rate: float


class NewsArticle(BaseModel):
    id: int
    title: str
    description: str
    category_id: int
    views: int
    publish_time: str

"""Schemas for search results."""
from pydantic import BaseModel

from app.schemas.document import ChunkRecord


class RankedChunk(BaseModel):
    """One chunk with its rank and a score that is only meaningful within its own score_type (never confidence)."""

    record: ChunkRecord
    rank: int  # 1 = best within this result list
    score: float
    score_type: str  # "bm25" or "cosine": different scales, never add or compare them directly

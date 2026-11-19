"""Schemas for search: internal ranked chunks, the /search request and response, and the reranker's structured output."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.filters import SearchFilters
from app.schemas.document import ChunkRecord


class RankedChunk(BaseModel):
    """One chunk with its rank and a score that is only meaningful within its own score_type (never confidence)."""

    record: ChunkRecord
    rank: int  # 1 = best within this result list
    score: float
    score_type: str  # "bm25", "cosine", "rrf" or "llm_relevance_0_10": different scales, never add or compare them
    stage: str  # which step produced this ranking: "lexical", "semantic", "fused_rrf" or "reranked"


class RerankScore(BaseModel):
    """The model's relevance score for one candidate excerpt."""

    candidate: int = Field(ge=1)
    relevance: int = Field(ge=0, le=10)


class RerankResult(BaseModel):
    """Structured output of the LLM reranking step."""

    scores: list[RerankScore]


class SearchRequest(BaseModel):
    """POST /search input; the corpus restriction is not an option, it is always applied in code."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    mode: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    """One returned chunk with source metadata; the score is labelled by type and is not a confidence value."""

    rank: int
    score: float
    score_type: str
    stage: str
    chunk_id: str
    doc_id: str
    title: str
    source_url: str
    locator_type: str
    locator: str  # e.g. "p. 2" or "pp. 2-3"
    article: str | None
    year: int | None
    doc_type: str | None
    status: str | None
    text: str


class SearchResponse(BaseModel):
    """POST /search output."""

    mode: str
    ranking_stage: str  # stage of the returned ranking
    filters_applied: SearchFilters
    results: list[SearchHit]
    candidates_before_rerank: list[str] | None = None  # chunk ids in fused order (hybrid only), to compare with results
    rerank_note: str | None = None  # set when reranking fell back to the fused order, and why

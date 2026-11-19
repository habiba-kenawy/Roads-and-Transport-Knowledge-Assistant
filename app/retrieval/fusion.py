"""Reciprocal Rank Fusion: merge ranked lists using ranks only, never raw scores (RAG-02)."""
from app.schemas.document import ChunkRecord
from app.schemas.search import RankedChunk

RRF_K = 60  # conventional smoothing constant: dampens the gap between rank 1 and rank 2


def rrf_fuse(ranked_lists: list[list[RankedChunk]], top_n: int) -> list[RankedChunk]:
    """Merge lists into one; a chunk found by several lists becomes a single entry (deduplication by chunk id)."""
    points: dict[str, float] = {}
    records: dict[str, ChunkRecord] = {}
    for ranked in ranked_lists:
        for hit in ranked:
            chunk_id = hit.record.chunk_id
            points[chunk_id] = points.get(chunk_id, 0.0) + 1.0 / (RRF_K + hit.rank)  # only the rank is used
            records[chunk_id] = hit.record
    order = sorted(points, key=lambda c: (-points[c], c))[:top_n]  # ties broken by id so results are deterministic
    return [RankedChunk(record=records[c], rank=n, score=points[c], score_type="rrf", stage="fused_rrf")
            for n, c in enumerate(order, start=1)]

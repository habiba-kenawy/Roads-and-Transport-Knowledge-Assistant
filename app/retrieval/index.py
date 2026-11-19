"""In-memory search index over the stored chunks: BM25 (lexical) and cosine similarity (semantic) (RAG-01, RAG-03)."""
import re
import sqlite3

import numpy as np
from rank_bm25 import BM25Okapi

from app.errors import IndexNotReadyError  # noqa: F401  (re-exported for callers)
from app.retrieval.filters import SearchFilters, matches
from app.schemas.document import ChunkRecord
from app.schemas.search import RankedChunk


def tokenize(text: str) -> list[str]:
    """Lowercase words and numbers only; deliberately no stemming or stop-words, to keep BM25 easy to explain."""
    return re.findall(r"\w+", text.lower())


class SearchIndex:
    """Chunks plus a BM25 model and (optionally) a unit-length embedding matrix, built once and reused."""

    def __init__(self, records: list[ChunkRecord], vectors: dict[str, np.ndarray] | None = None) -> None:
        if not records:
            raise IndexNotReadyError("no chunks indexed; run POST /ingest first")
        self.records = records
        self.bm25 = BM25Okapi([tokenize(r.text) for r in records])
        self.matrix: np.ndarray | None = None
        if vectors and all(r.chunk_id in vectors for r in records):
            raw = np.vstack([vectors[r.chunk_id] for r in records])
            self.matrix = raw / np.linalg.norm(raw, axis=1, keepdims=True)  # unit length: dot product = cosine

    def allowed(self, filters: SearchFilters) -> np.ndarray:
        """Boolean mask of chunks passing the corpus boundary and filters; every mode ranks only these."""
        return np.array([matches(r, filters) for r in self.records])


def load_index(conn: sqlite3.Connection, model: str) -> SearchIndex:
    """Read chunks and embeddings from SQLite into a SearchIndex."""
    conn.row_factory = sqlite3.Row
    records = [ChunkRecord(**dict(r)) for r in conn.execute("SELECT * FROM chunks ORDER BY doc_id, chunk_index")]
    vectors = {r["chunk_id"]: np.frombuffer(r["vector"], dtype=np.float32)
               for r in conn.execute("SELECT chunk_id, vector FROM embeddings WHERE model = ?", (model,))}
    return SearchIndex(records, vectors)


def top_ranked(index: SearchIndex, scores: np.ndarray, mask: np.ndarray, top_k: int, score_type: str, stage: str, min_score: float | None) -> list[RankedChunk]:
    """Pick the best allowed chunks; disallowed chunks are excluded BEFORE the top-k cut, so filters never shrink results."""
    candidates = [i for i in np.argsort(-scores) if mask[i] and (min_score is None or scores[i] > min_score)][:top_k]
    return [RankedChunk(record=index.records[i], rank=n, score=float(scores[i]), score_type=score_type, stage=stage)
            for n, i in enumerate(candidates, start=1)]


def lexical_search(index: SearchIndex, query: str, filters: SearchFilters, top_k: int) -> list[RankedChunk]:
    """BM25 ranking; chunks sharing no word with the query (score 0) are not returned."""
    scores = np.asarray(index.bm25.get_scores(tokenize(query)))
    return top_ranked(index, scores, index.allowed(filters), top_k, "bm25", "lexical", min_score=0.0)


def semantic_search(index: SearchIndex, embedder, query: str, filters: SearchFilters, top_k: int) -> list[RankedChunk]:
    """Cosine-similarity ranking of the query embedding against the chunk embeddings."""
    if index.matrix is None:
        raise IndexNotReadyError("embeddings are missing; run POST /ingest with the model configured")
    q = np.asarray(embedder.embed_query(query), dtype=np.float32)
    scores = index.matrix @ (q / np.linalg.norm(q))
    return top_ranked(index, scores, index.allowed(filters), top_k, "cosine", "semantic", min_score=None)

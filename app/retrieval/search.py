"""Search service: runs a mode (lexical / semantic / hybrid) and builds the /search response (RAG-01..04)."""
import sqlite3
from pathlib import Path

from app.config import Settings
from app.errors import IndexNotReadyError, ModelCallError
from app.llm import make_chat_model
from app.retrieval.embeddings import make_embedder
from app.retrieval.fusion import rrf_fuse
from app.retrieval.index import SearchIndex, lexical_search, load_index, semantic_search
from app.retrieval.rerank import rerank
from app.schemas.search import RankedChunk, SearchHit, SearchRequest, SearchResponse


class IndexCache:
    """Keep the in-memory index and reload it when the SQLite file changes (for example after /ingest)."""

    def __init__(self) -> None:
        self._index: SearchIndex | None = None
        self._stamp: int | None = None

    def get(self, settings: Settings) -> SearchIndex:
        """Return the current index, rebuilding it if the database file is new or changed."""
        path = Path(settings.db_path)
        if not path.is_file():
            raise IndexNotReadyError("no index yet; run POST /ingest first")
        stamp = path.stat().st_mtime_ns
        if self._index is None or stamp != self._stamp:
            conn = sqlite3.connect(path)
            try:
                self._index = load_index(conn, settings.embedding_deployment)
            except sqlite3.OperationalError as exc:  # file exists but has no tables
                raise IndexNotReadyError("index file is empty; run POST /ingest first") from exc
            finally:
                conn.close()
            self._stamp = stamp
        return self._index


INDEX_CACHE = IndexCache()


def locator_text(start: int, end: int) -> str:
    """Format a page range the way a citation shows it."""
    return f"p. {start}" if start == end else f"pp. {start}-{end}"


def to_hit(ranked: RankedChunk) -> SearchHit:
    """Convert an internal ranked chunk into the public search hit."""
    r = ranked.record
    return SearchHit(rank=ranked.rank, score=ranked.score, score_type=ranked.score_type, stage=ranked.stage,
                     chunk_id=r.chunk_id, doc_id=r.doc_id, title=r.title, source_url=r.source_url,
                     locator_type=r.locator_type, locator=locator_text(r.page_start, r.page_end), article=r.article,
                     year=r.year, doc_type=r.doc_type, status=r.status, text=r.text)


def checked_semantic_search(index: SearchIndex, embedder, query: str, filters, top_k: int) -> list[RankedChunk]:
    """Semantic search where a failed model call becomes a ModelCallError (shared by /search and the graph)."""
    try:
        return semantic_search(index, embedder, query, filters, top_k)
    except IndexNotReadyError:
        raise  # a missing embeddings table is a different problem from a failed model call
    except Exception as exc:  # network, quota or timeout while embedding the question
        raise ModelCallError(f"embedding call failed: {type(exc).__name__}") from exc


def perform_search(settings: Settings, request: SearchRequest, index: SearchIndex | None = None,
                   embedder=None, llm=None) -> SearchResponse:
    """Run the requested mode. Filters and the corpus boundary are applied inside each retriever, before ranking."""
    index = index or INDEX_CACHE.get(settings)
    filters, top_k, query = request.filters, request.top_k, request.query
    base = dict(mode=request.mode, filters_applied=filters)
    if request.mode == "lexical":
        results = lexical_search(index, query, filters, top_k)
        return SearchResponse(**base, ranking_stage="lexical", results=[to_hit(r) for r in results])
    embedder = embedder or make_embedder(settings)  # raises ModelNotConfiguredError, which passes through untouched
    pool = max(settings.retrieval_candidates, top_k)  # never fewer candidates than the top_k asked for
    wanted = pool if request.mode == "hybrid" else top_k
    semantic = checked_semantic_search(index, embedder, query, filters, wanted)
    if request.mode == "semantic":
        return SearchResponse(**base, ranking_stage="semantic", results=[to_hit(r) for r in semantic])
    lexical = lexical_search(index, query, filters, pool)
    fused = rrf_fuse([lexical, semantic], top_n=pool)
    try:
        llm = llm or make_chat_model(settings)
    except Exception as exc:  # no chat model: still return the fused order and say so
        final, note = fused[:top_k], f"reranking unavailable ({type(exc).__name__}); fused order returned"
    else:
        final, note = rerank(llm, query, fused, top_k)
    return SearchResponse(**base, ranking_stage=final[0].stage if final else "reranked", results=[to_hit(r) for r in final],
                          candidates_before_rerank=[r.record.chunk_id for r in fused], rerank_note=note)

"""Build the full searchable index: ingest documents, then embed their chunks.

Lives outside both `ingestion` and `retrieval` so neither folder has to import the other.
"""
import logging
from pathlib import Path

from app.config import Settings
from app.ingestion.pipeline import ingest_all
from app.ingestion.store import connect
from app.retrieval.embeddings import embed_missing, make_embedder
from app.schemas.ingest import IngestReport

logger = logging.getLogger(__name__)


def embed_chunks(conn, settings: Settings, embedder) -> tuple[int, str | None]:
    """Embed new chunks if the model is available; a failure here is reported and never undoes ingestion."""
    embedder = embedder or (make_embedder(settings) if settings.model_configured else None)
    if embedder is None:
        return 0, "embedding model not configured; semantic search unavailable"
    try:
        return embed_missing(conn, embedder, settings.embedding_deployment), None
    except Exception as exc:  # network/quota problems must not undo a successful ingestion
        logger.error("embedding failed error=%s", type(exc).__name__)
        return 0, f"embedding failed: {type(exc).__name__}"


def build_index(settings: Settings, manifest_path: Path = Path("data/manifest.csv"),
                raw_dir: Path = Path("data/raw"), embedder=None) -> IngestReport:
    """Ingest all approved documents, then embed new chunks, and return one combined report."""
    report = ingest_all(settings, manifest_path, raw_dir)
    conn = connect(settings.db_path)
    try:
        embedded, embedding_error = embed_chunks(conn, settings, embedder)
    finally:
        conn.close()
    return report.model_copy(update={"embedded": embedded, "embedding_error": embedding_error})

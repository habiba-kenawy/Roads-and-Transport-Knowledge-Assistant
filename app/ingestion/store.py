"""Stable chunk IDs and the SQLite chunk store (DATA-04, DATA-05)."""
import hashlib
import sqlite3
from pathlib import Path

from app.schemas.document import Chunk, ChunkRecord
from app.schemas.manifest import ManifestRecord

COLUMNS = list(ChunkRecord.model_fields)  # table columns mirror the model, so they cannot drift apart
CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS chunks ("
    "chunk_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, chunk_index INTEGER NOT NULL, title TEXT NOT NULL, "
    "source_url TEXT NOT NULL, primary_category TEXT NOT NULL, locator_type TEXT NOT NULL, "
    "page_start INTEGER NOT NULL, page_end INTEGER NOT NULL, article TEXT, text TEXT NOT NULL, "
    "doc_type TEXT, number TEXT, year INTEGER, authority TEXT, status TEXT)"
)
CREATE_DOCUMENTS = "CREATE TABLE IF NOT EXISTS documents (doc_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL)"
CREATE_EMBEDDINGS = "CREATE TABLE IF NOT EXISTS embeddings (chunk_id TEXT PRIMARY KEY, model TEXT NOT NULL, vector BLOB NOT NULL)"
INSERT = f"INSERT INTO chunks ({', '.join(COLUMNS)}) VALUES ({', '.join(':' + c for c in COLUMNS)})"


def make_chunk_id(doc_id: str, index: int, text: str) -> str:
    """Same document, position and text always give the same id; a changed text gives a new one."""
    return f"{doc_id}-{index:03d}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]}"


def build_records(doc: ManifestRecord, chunks: list[Chunk]) -> list[ChunkRecord]:
    """Attach the document's metadata and a stable id to each chunk."""
    return [
        ChunkRecord(chunk_id=make_chunk_id(doc.doc_id, i, c.text), doc_id=doc.doc_id, chunk_index=i, title=doc.title,
                    source_url=doc.source_url, primary_category=doc.primary_category, locator_type="page",
                    page_start=c.page_start, page_end=c.page_end, article=c.article, text=c.text,
                    doc_type=doc.doc_type, number=doc.number, year=doc.year, authority=doc.authority,
                    status=doc.status)
        for i, c in enumerate(chunks)
    ]


def connect(db_path: str) -> sqlite3.Connection:
    """Open (and create if needed) the SQLite file with its tables."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(CREATE_TABLE)
    conn.execute(CREATE_DOCUMENTS)
    conn.execute(CREATE_EMBEDDINGS)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)")
    return conn


def get_fingerprint(conn: sqlite3.Connection, doc_id: str) -> str | None:
    """Return what the stored chunks of this document were built from, or None if it was never ingested."""
    row = conn.execute("SELECT fingerprint FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return row[0] if row else None


def replace_document_chunks(conn: sqlite3.Connection, doc_id: str, records: list[ChunkRecord], fingerprint: str) -> None:
    """Swap a document's chunks and fingerprint in one transaction: no duplicates, no stale rows, no half updates."""
    with conn:  # commits on success, rolls back on error
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        conn.executemany(INSERT, [r.model_dump() for r in records])
        conn.execute("INSERT OR REPLACE INTO documents (doc_id, fingerprint) VALUES (?, ?)", (doc_id, fingerprint))


def purge_unlisted(conn: sqlite3.Connection, keep_ids: list[str]) -> None:
    """Delete documents that are no longer approved in the manifest, so the corpus boundary also holds in the index."""
    marks = ",".join("?" * len(keep_ids))
    with conn:
        conn.execute(f"DELETE FROM chunks WHERE doc_id NOT IN ({marks})", keep_ids)
        conn.execute(f"DELETE FROM documents WHERE doc_id NOT IN ({marks})", keep_ids)


def index_available(db_path: str) -> bool:
    """True when the SQLite file exists and holds at least one chunk (used by /health)."""
    if not Path(db_path).is_file():
        return False
    try:
        with sqlite3.connect(db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] > 0
    except sqlite3.Error:
        return False

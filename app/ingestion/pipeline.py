"""Ingest every accepted manifest document into SQLite; unchanged documents are skipped (DATA-02, DATA-05)."""
import hashlib
import logging
from pathlib import Path

from app.config import Settings
from app.ingestion.chunker import split_articles
from app.ingestion.cleaner import clean_pages
from app.ingestion.manifest import load_manifest
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.store import build_records, connect, get_fingerprint, purge_unlisted, replace_document_chunks
from app.schemas.ingest import IngestError, IngestReport

logger = logging.getLogger(__name__)


def fingerprint(pdf: Path, settings: Settings) -> str:
    """Describe what stored chunks were built from: the file's bytes and the chunking settings."""
    return f"{hashlib.sha256(pdf.read_bytes()).hexdigest()}:{settings.chunk_size}:{settings.chunk_overlap}"


def ingest_all(settings: Settings, manifest_path: Path = Path("data/manifest.csv"), raw_dir: Path = Path("data/raw")) -> IngestReport:
    """Index all approved documents; a failure is recorded and never stops the others."""
    accepted, rejected = load_manifest(manifest_path, raw_dir)
    errors = [IngestError(doc_id=r.doc_id, reason="; ".join(r.reasons)) for r in rejected]  # excluded rows count as failed
    indexed = skipped = 0
    conn = connect(settings.db_path)
    try:
        for doc in accepted:
            pdf = raw_dir / doc.file_name
            try:
                stamp = fingerprint(pdf, settings)
                if get_fingerprint(conn, doc.doc_id) == stamp:
                    skipped += 1
                    continue
                chunks = split_articles(clean_pages(parse_pdf(pdf)), settings.chunk_size, settings.chunk_overlap)
                if not chunks:
                    raise ValueError("no text extracted")
                replace_document_chunks(conn, doc.doc_id, build_records(doc, chunks), stamp)
                indexed += 1
                logger.info("indexed doc_id=%s chunks=%s", doc.doc_id, len(chunks))
            except Exception as exc:  # one bad document must not stop the rest
                logger.error("ingest failed doc_id=%s error=%s", doc.doc_id, type(exc).__name__)
                errors.append(IngestError(doc_id=doc.doc_id, reason=f"{type(exc).__name__}: {exc}"))
        purge_unlisted(conn, [d.doc_id for d in accepted])
    finally:
        conn.close()
    logger.info("ingest done indexed=%s skipped=%s failed=%s", indexed, skipped, len(errors))
    return IngestReport(indexed=indexed, skipped=skipped, failed=len(errors), errors=errors)

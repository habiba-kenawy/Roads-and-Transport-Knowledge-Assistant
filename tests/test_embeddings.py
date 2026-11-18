"""Tests for embedding storage with a FAKE embedder that counts its calls (no real model is called)."""
from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.store import build_records, connect, replace_document_chunks
from app.retrieval.embeddings import ModelNotConfiguredError, embed_missing, make_embedder
from app.schemas.document import Chunk
from app.schemas.manifest import ManifestRecord

DOC = ManifestRecord(doc_id="fake-1", file_name="f.pdf", title="FAKE", source_url="https://fake.example",
                     content_url="https://fake.example/a.pdf", primary_category="Roads and Transport", language="English",
                     retrieval_date="2000-01-01", doc_type="", number="", year="", authority="", status="",
                     issue_date="", notes="")


class CountingEmbedder:
    """FAKE embedder: returns a 3-number vector per text and records how many texts it was asked to embed."""

    def __init__(self) -> None:
        self.texts_seen = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.texts_seen += len(texts)
        return [[float(len(t)), 1.0, 0.5] for t in texts]


def store(conn, *texts: str) -> None:
    """Store FAKE chunks for the fake document."""
    chunks = [Chunk(article=None, text=t, page_start=1, page_end=1) for t in texts]
    replace_document_chunks(conn, "fake-1", build_records(DOC, chunks), "fp")


def test_embed_missing_embeds_once_and_is_idempotent(tmp_path: Path) -> None:
    """Running the embedding step twice must not call the model again for unchanged chunks."""
    conn = connect(str(tmp_path / "t.sqlite"))
    store(conn, "one", "two", "three")
    embedder = CountingEmbedder()
    assert embed_missing(conn, embedder, "fake-model") == 3
    assert embed_missing(conn, embedder, "fake-model") == 0
    assert embedder.texts_seen == 3
    assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 3


def test_vectors_of_removed_or_changed_chunks_are_dropped(tmp_path: Path) -> None:
    """No stale vectors: a changed text gets a new chunk id, and the old vector must disappear."""
    conn = connect(str(tmp_path / "t.sqlite"))
    store(conn, "one", "two")
    embed_missing(conn, CountingEmbedder(), "fake-model")
    store(conn, "one", "two changed")
    embedder = CountingEmbedder()
    assert embed_missing(conn, embedder, "fake-model") == 1
    assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 2


def test_changing_the_embedding_model_re_embeds_everything(tmp_path: Path) -> None:
    """Vectors from a different model are not comparable, so they must be replaced."""
    conn = connect(str(tmp_path / "t.sqlite"))
    store(conn, "one", "two")
    embed_missing(conn, CountingEmbedder(), "model-a")
    assert embed_missing(conn, CountingEmbedder(), "model-b") == 2


def test_make_embedder_without_credentials_raises_controlled_error() -> None:
    """Missing credentials give ModelNotConfiguredError, which the API will map to a clear response."""
    with pytest.raises(ModelNotConfiguredError):
        make_embedder(Settings(_env_file=None, azure_openai_endpoint=None, azure_openai_api_key=None))

"""Tests for build_index (ingest + embed) with FAKE data and FAKE embedders; no real model is called."""
from app.indexing import build_index
from tests.test_pipeline import fake_row, setup


class FakeEmbedder:
    """FAKE embedder that returns a tiny vector per text."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class BrokenEmbedder:
    """FAKE embedder that always fails, to test controlled handling."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("FAKE network failure")


def test_build_index_embeds_new_chunks_and_second_run_embeds_nothing(tmp_path, monkeypatch) -> None:
    """Semantic search needs vectors: they are created once and not repeated for unchanged chunks."""
    manifest, raw, settings = setup(tmp_path, [fake_row("a")], monkeypatch)
    first = build_index(settings, manifest, raw, embedder=FakeEmbedder())
    second = build_index(settings, manifest, raw, embedder=FakeEmbedder())
    assert first.indexed == 1 and first.embedded == 2 and first.embedding_error is None
    assert second.skipped == 1 and second.embedded == 0


def test_embedding_failure_is_reported_but_ingestion_still_succeeds(tmp_path, monkeypatch) -> None:
    """A model/network problem must not undo or hide the chunks that were indexed."""
    manifest, raw, settings = setup(tmp_path, [fake_row("a")], monkeypatch)
    report = build_index(settings, manifest, raw, embedder=BrokenEmbedder())
    assert report.indexed == 1 and report.embedded == 0
    assert "ConnectionError" in report.embedding_error


def test_missing_credentials_are_reported_not_raised(tmp_path, monkeypatch) -> None:
    """Without a configured model, ingestion works and says semantic search is unavailable."""
    manifest, raw, settings = setup(tmp_path, [fake_row("a")], monkeypatch)
    report = build_index(settings, manifest, raw)
    assert report.indexed == 1 and "not configured" in report.embedding_error

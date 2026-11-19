"""Tests for perform_search, the index cache and POST /search. All data is FAKE; models are FAKES."""
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.config import Settings
from app.errors import IndexNotReadyError, ModelCallError, ModelNotConfiguredError
from app.ingestion.store import build_records, connect, replace_document_chunks
from app.retrieval.filters import SearchFilters
from app.retrieval.search import IndexCache, perform_search
from app.schemas.document import Chunk
from app.schemas.manifest import ManifestRecord
from app.schemas.search import SearchRequest, SearchResponse
from tests.test_fusion_rerank import FakeLLM
from tests.test_search import INDEX, FakeEmbedder

SETTINGS = Settings(_env_file=None, retrieval_candidates=5)


def request(**kw) -> SearchRequest:
    """Build a FAKE search request."""
    return SearchRequest(**{"query": "toll", **kw})


def reverse_llm(n: int = 5) -> FakeLLM:
    """FAKE model that prefers the LAST candidate, so reranking visibly changes the order."""
    return FakeLLM({i: i for i in range(1, n + 1)})


def test_lexical_and_semantic_modes_return_labelled_hits_with_locators() -> None:
    """RAG-01: each mode is selectable and results carry mode, stage, score type and a page locator."""
    lex = perform_search(SETTINGS, request(mode="lexical"), INDEX, FakeEmbedder())
    sem = perform_search(SETTINGS, request(mode="semantic"), INDEX, FakeEmbedder())
    assert (lex.mode, lex.ranking_stage, {h.score_type for h in lex.results}) == ("lexical", "lexical", {"bm25"})
    assert (sem.mode, sem.ranking_stage, {h.score_type for h in sem.results}) == ("semantic", "semantic", {"cosine"})
    assert lex.results[0].locator == "p. 1" and lex.candidates_before_rerank is None


def test_hybrid_fuses_then_reranks_and_exposes_the_order_before_reranking() -> None:
    """RAG-02/04, AT-05: fused candidates, then a separate reranked order; both are visible."""
    out = perform_search(SETTINGS, request(query="toll fine parking vehicle", mode="hybrid", top_k=3), INDEX, FakeEmbedder(), reverse_llm())
    assert out.ranking_stage == "reranked" and {h.score_type for h in out.results} == {"llm_relevance_0_10"}
    before = out.candidates_before_rerank
    assert len(before) == 5  # retrieval_candidates=5 and the fake embedder scores every chunk
    assert out.results[0].chunk_id == before[-1]  # the fake model prefers the last fused candidate
    assert [h.chunk_id for h in out.results] != before[:3]  # reranking changed the order
    assert out.rerank_note is None


def test_hybrid_falls_back_to_fused_order_when_the_model_fails() -> None:
    """A reranker failure is reported in rerank_note and the fused order is returned."""
    out = perform_search(SETTINGS, request(mode="hybrid", top_k=3), INDEX, FakeEmbedder(), FakeLLM(error=TimeoutError("FAKE")))
    assert out.ranking_stage == "fused_rrf" and "TimeoutError" in out.rerank_note and len(out.results) == 3


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_filters_and_category_boundary_hold_in_every_mode(mode: str) -> None:
    """AT-04/RAG-03: every returned chunk satisfies the filters, and the out-of-category chunk never appears."""
    out = perform_search(SETTINGS, request(query="toll fine parking licence", mode=mode, filters=SearchFilters(year=2023), top_k=5),
                         INDEX, FakeEmbedder(), reverse_llm())
    assert out.results and all(h.year == 2023 for h in out.results)
    plain = perform_search(SETTINGS, request(query="toll", mode=mode, top_k=20), INDEX, FakeEmbedder(), reverse_llm())
    assert "traffic" not in [h.chunk_id for h in plain.results]


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_no_match_filter_returns_empty_results_in_every_mode(mode: str) -> None:
    """AT-04: a filter nothing satisfies gives an empty list, not an error."""
    out = perform_search(SETTINGS, request(mode=mode, filters=SearchFilters(year=1999)), INDEX, FakeEmbedder(), reverse_llm())
    assert out.results == []


def test_embedding_failure_becomes_a_controlled_model_call_error() -> None:
    """A network failure while embedding the question is reported as ModelCallError, naming only the error type."""
    class Broken:
        def embed_query(self, text):
            raise ConnectionError("FAKE network down")

    with pytest.raises(ModelCallError, match="ConnectionError"):
        perform_search(SETTINGS, request(mode="semantic"), INDEX, Broken())


def test_missing_credentials_raise_model_not_configured_for_semantic_modes() -> None:
    """Without a configured model, semantic and hybrid give a clear error (lexical still works)."""
    with pytest.raises(ModelNotConfiguredError):
        perform_search(SETTINGS, request(mode="semantic"), INDEX)
    assert perform_search(SETTINGS, request(mode="lexical"), INDEX).results


def test_index_cache_reloads_after_the_database_changes(tmp_path: Path) -> None:
    """After /ingest the cached index must not stay stale."""
    doc = ManifestRecord(doc_id="fake-1", file_name="f.pdf", title="FAKE", source_url="https://fake.example",
                         content_url="https://fake.example/a.pdf", primary_category="Roads and Transport", language="English",
                         retrieval_date="2000-01-01", doc_type="", number="", year="", authority="", status="", issue_date="", notes="")
    settings = Settings(_env_file=None, db_path=str(tmp_path / "t.sqlite"))
    conn = connect(settings.db_path)
    replace_document_chunks(conn, "fake-1", build_records(doc, [Chunk(article=None, text="one", page_start=1, page_end=1)]), "fp")
    conn.close()
    cache = IndexCache()
    assert len(cache.get(settings).records) == 1
    conn = sqlite3.connect(settings.db_path)
    replace_document_chunks(conn, "fake-1", build_records(doc, [Chunk(article=None, text=t, page_start=1, page_end=1) for t in ("one", "two")]), "fp2")
    conn.close()
    later = os.stat(settings.db_path).st_mtime_ns + 5_000_000_000
    os.utime(settings.db_path, ns=(later, later))  # make the change visible even on coarse file clocks
    assert len(cache.get(settings).records) == 2


def test_index_cache_reports_missing_or_empty_database(tmp_path: Path) -> None:
    """No file, or a file without tables, gives IndexNotReadyError (a controlled error), not a crash."""
    with pytest.raises(IndexNotReadyError):
        IndexCache().get(Settings(_env_file=None, db_path=str(tmp_path / "missing.sqlite")))
    (tmp_path / "empty.sqlite").write_bytes(b"")
    with pytest.raises(IndexNotReadyError):
        IndexCache().get(Settings(_env_file=None, db_path=str(tmp_path / "empty.sqlite")))


client = TestClient(main.app)


@pytest.mark.parametrize("body", [
    {"query": ""}, {"query": "   "}, {"query": "x" * 501}, {"query": "toll", "top_k": 0}, {"query": "toll", "top_k": 21},
    {"query": "toll", "mode": "fuzzy"}, {"query": "toll", "filters": {"year": 3000}}, {"query": "toll", "filters": {"year": "abc"}},
    {},
])
def test_search_route_rejects_invalid_requests_with_422(body) -> None:
    """AT-11: empty query, bad top_k, unsupported mode and invalid filters give controlled validation errors."""
    assert client.post("/search", json=body).status_code == 422


def test_search_route_returns_the_service_response(monkeypatch) -> None:
    """The route is thin: it passes the validated request to the service and returns its response."""
    fake = SearchResponse(mode="lexical", ranking_stage="lexical", filters_applied=SearchFilters(), results=[])
    monkeypatch.setattr(main, "perform_search", lambda settings, req: fake)
    response = client.post("/search", json={"query": "toll", "mode": "lexical"})
    assert response.status_code == 200 and response.json()["mode"] == "lexical"


@pytest.mark.parametrize("error, status", [(IndexNotReadyError("no index"), 503), (ModelNotConfiguredError("no key"), 503),
                                           (ModelCallError("embedding call failed: Timeout"), 502)])
def test_search_route_maps_known_errors_to_controlled_responses(monkeypatch, error, status) -> None:
    """Index and model problems become clear 503/502 responses with a message, never a stack trace."""
    def boom(settings, req):
        raise error

    monkeypatch.setattr(main, "perform_search", boom)
    response = client.post("/search", json={"query": "toll"})
    assert response.status_code == status and response.json()["detail"] == str(error)

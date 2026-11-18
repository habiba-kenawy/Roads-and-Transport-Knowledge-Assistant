"""Tests for lexical and semantic search. All records are FAKE and the embedder is a deterministic FAKE."""
import numpy as np
import pytest

from app.retrieval.filters import SearchFilters
from app.retrieval.index import IndexNotReadyError, SearchIndex, lexical_search, semantic_search
from app.schemas.document import ChunkRecord

VOCAB = ["toll", "fine", "parking", "vehicle", "metro", "licence"]


def rec(chunk_id: str, text: str, year: int | None = 2020, doc_type: str | None = "Law", category: str = "Roads and Transport") -> ChunkRecord:
    """Build a FAKE chunk record."""
    return ChunkRecord(chunk_id=chunk_id, doc_id="fake", chunk_index=0, title="FAKE", source_url="https://fake.example",
                       primary_category=category, locator_type="page", page_start=1, page_end=1, article=None,
                       text=text, doc_type=doc_type, number=None, year=year, authority=None, status=None)


class FakeEmbedder:
    """Deterministic FAKE embedder: counts how often each vocabulary word appears (plus a tiny constant)."""

    def vec(self, text: str) -> list[float]:
        words = text.lower().split()
        return [float(words.count(w)) + 0.001 for w in VOCAB]

    def embed_query(self, text: str) -> list[float]:
        return self.vec(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.vec(t) for t in texts]


RECORDS = [
    rec("toll", "toll toll gate fee for each vehicle", 2020, "Law"),
    rec("fine", "fine for illegal parking", 2023, "Resolution"),
    rec("metro", "metro station opening hours", 2020, "Resolution"),
    rec("licence", "licence renewal for a taxi driver", 2023, "Law"),
    rec("misc1", "general provisions and definitions", 2020, "Law"),
    rec("misc2", "publication in the official gazette", 2023, "Law"),
    rec("traffic", "toll toll toll outside the corpus", 2020, "Law", category="Traffic"),
]
VECTORS = {r.chunk_id: np.array(FakeEmbedder().vec(r.text), dtype=np.float32) for r in RECORDS}
INDEX = SearchIndex(RECORDS, VECTORS)


def ids(hits) -> list[str]:
    """Return chunk ids in rank order."""
    return [h.record.chunk_id for h in hits]


def test_lexical_finds_exact_term_first_and_labels_scores() -> None:
    """RAG-01: BM25 ranks the chunk containing the query word first; score type is labelled."""
    hits = lexical_search(INDEX, "toll", SearchFilters(), top_k=5)
    assert ids(hits)[0] == "toll"
    assert [h.rank for h in hits] == list(range(1, len(hits) + 1))
    assert {h.score_type for h in hits} == {"bm25"}


def test_lexical_returns_nothing_when_no_word_matches() -> None:
    """A query with no shared words returns an empty list, not arbitrary chunks."""
    assert lexical_search(INDEX, "helicopter", SearchFilters(), top_k=5) == []


def test_filters_are_applied_before_top_k_in_lexical_mode() -> None:
    """RAG-03: with year=2023 the best 2020 chunk must not appear and top_k still fills from allowed chunks."""
    hits = lexical_search(INDEX, "toll fine parking licence", SearchFilters(year=2023), top_k=2)
    assert len(hits) == 2 and all(h.record.year == 2023 for h in hits)


def test_out_of_category_chunk_is_never_returned_lexical_or_semantic() -> None:
    """RAG-03/AT-01: the Traffic chunk matches 'toll' best but must never be returned in any mode."""
    assert "traffic" not in ids(lexical_search(INDEX, "toll", SearchFilters(), top_k=10))
    assert "traffic" not in ids(semantic_search(INDEX, FakeEmbedder(), "toll", SearchFilters(), top_k=10))


def test_top_k_limits_results() -> None:
    """The result list never exceeds top_k."""
    assert len(lexical_search(INDEX, "toll fine parking", SearchFilters(), top_k=1)) == 1


def test_semantic_ranks_nearest_vector_first_and_labels_scores() -> None:
    """RAG-01: cosine ranking puts the chunk about 'parking' first for a parking query."""
    hits = semantic_search(INDEX, FakeEmbedder(), "parking fine", SearchFilters(), top_k=3)
    assert ids(hits)[0] == "fine"
    assert {h.score_type for h in hits} == {"cosine"}


def test_semantic_filters_apply_before_top_k() -> None:
    """RAG-03: filtering by doc_type=Resolution still returns top_k results among Resolutions only."""
    hits = semantic_search(INDEX, FakeEmbedder(), "toll", SearchFilters(doc_type="Resolution"), top_k=2)
    assert len(hits) == 2 and all(h.record.doc_type == "Resolution" for h in hits)


def test_no_match_filter_returns_empty_in_both_modes() -> None:
    """AT-04: a filter nothing satisfies gives empty results in every mode."""
    f = SearchFilters(year=1999)
    assert lexical_search(INDEX, "toll", f, top_k=5) == []
    assert semantic_search(INDEX, FakeEmbedder(), "toll", f, top_k=5) == []


def test_semantic_search_without_embeddings_raises_controlled_error() -> None:
    """Missing embeddings give a clear, catchable error rather than a crash."""
    with pytest.raises(IndexNotReadyError):
        semantic_search(SearchIndex(RECORDS, None), FakeEmbedder(), "toll", SearchFilters(), top_k=3)


def test_empty_index_raises_controlled_error() -> None:
    """An empty chunk store (nothing ingested) is reported clearly."""
    with pytest.raises(IndexNotReadyError):
        SearchIndex([], None)

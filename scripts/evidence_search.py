"""AT-03 and AT-04 evidence: same question in three modes, and filters in every mode (real models, real index).

Usage: python -m scripts.evidence_search
"""
from pathlib import Path

from app.config import Settings
from app.retrieval.filters import SearchFilters
from app.retrieval.search import perform_search
from app.schemas.search import SearchRequest

MODES = ("lexical", "semantic", "hybrid")


def at03(settings: Settings) -> str:
    """Run two questions in all modes and list each ranked result with its stage and labelled score."""
    out = ["AT-03 search modes: same question, three modes (top 5, no filters)\n",
           "Scores are labelled by type and are NOT comparable across modes (bm25, cosine, rrf, llm_relevance_0_10).\n"]
    for question in ("Can a driver carry passengers in a vehicle that the licensing authority has not licensed to transport passengers?",
                     "Which railway violations require a written warning before a fine can be imposed?"):
        out.append(f"\nQUESTION: {question}")
        for mode in MODES:
            resp = perform_search(settings, SearchRequest(query=question, mode=mode, top_k=5))
            out.append(f"  mode={mode} ranking_stage={resp.ranking_stage}" + (f" rerank_note={resp.rerank_note}" if resp.rerank_note else ""))
            for h in resp.results:
                out.append(f"    #{h.rank} {h.score_type}={h.score:.3f} | {h.doc_id:<9} {str(h.article):<12} {h.locator:<9} | {h.status} | {h.title[:48]}")
            if resp.candidates_before_rerank:
                out.append(f"    fused order before rerank (first 8): {resp.candidates_before_rerank[:8]}")
    return "\n".join(out)


def at04(settings: Settings) -> str:
    """Apply each filter alone, both together, and a no-match filter in every mode; check every returned chunk."""
    cases = [("year=2023", SearchFilters(year=2023)), ("doc_type=Law", SearchFilters(doc_type="Law")),
             ("year=2023 AND doc_type=Law", SearchFilters(year=2023, doc_type="Law")),
             ("year=2026 AND doc_type=Law (no such document)", SearchFilters(year=2026, doc_type="Law"))]
    out = ["AT-04 filters: each filter, the combination and a no-match filter, in every mode (query: 'permit requirements and penalties', top_k=5)\n"]
    for label, filters in cases:
        for mode in MODES:
            resp = perform_search(settings, SearchRequest(query="permit requirements and penalties", mode=mode, filters=filters, top_k=5))
            ok = all((filters.year is None or h.year == filters.year) and (filters.doc_type is None or (h.doc_type or "").lower() == filters.doc_type.lower())
                     for h in resp.results)
            docs = sorted({(h.doc_id, h.year, h.doc_type) for h in resp.results})
            out.append(f"{label:<46} {mode:<9} returned={len(resp.results)} all_satisfy_filters={ok} docs={docs}")
    return "\n".join(out)


def main() -> None:
    """Write both evidence files and print them."""
    settings = Settings()
    for name, text in (("AT-03_search_modes.txt", at03(settings)), ("AT-04_filters.txt", at04(settings))):
        Path("evidence", name).write_text(text + "\n", encoding="utf-8")
        print(text, "\n")


if __name__ == "__main__":
    main()

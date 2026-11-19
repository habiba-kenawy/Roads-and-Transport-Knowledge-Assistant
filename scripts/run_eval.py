"""AT-12: run the evaluation questions in every mode and report whether the expected document is in the final top 5.

Usage: python -m scripts.run_eval   (needs the real index and model credentials; makes real model calls)
"""
import json
from pathlib import Path

from app.config import Settings
from app.retrieval.search import perform_search
from app.schemas.search import SearchRequest

MODES = ("lexical", "semantic", "hybrid")


def main(questions_path: Path = Path("data/eval_questions.json"), out_path: Path = Path("evidence/AT-12_eval.txt")) -> None:
    """Run every question in every mode; print and save a pass/fail table plus what ranked instead on a miss."""
    settings = Settings()
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    lines, totals = [], dict.fromkeys(MODES, 0)
    for q in questions:
        lines.append(f"{q['id']}: {q['question']}\n   expected: {q['expected_doc_ids']}  ({q['source_passage'][:90]}...)")
        for mode in MODES:
            resp = perform_search(settings, SearchRequest(query=q["question"], mode=mode, top_k=5))
            docs = [h.doc_id for h in resp.results]
            found = [d for d in q["expected_doc_ids"] if d in docs]
            totals[mode] += bool(found)
            where = f"rank {docs.index(found[0]) + 1}" if found else "MISS"
            note = f" | rerank_note: {resp.rerank_note}" if resp.rerank_note else ""
            lines.append(f"   {mode:<9} {where:<7} top5 docs: {docs}{note}")
    lines.append(f"\nSUMMARY: expected document in final top 5 -> " + " | ".join(f"{m}: {totals[m]}/{len(questions)}" for m in MODES))
    text = "\n".join(lines)
    print(text)
    out_path.write_text("AT-12 retrieval evaluation (document-level, top 5, no filters)\n\n" + text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

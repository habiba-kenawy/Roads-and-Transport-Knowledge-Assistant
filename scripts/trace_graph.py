"""AT-05 evidence: run the real graph (real models) and record a timed node trace, the plan, and the order before/after reranking.

Usage: python -m scripts.trace_graph   (makes real model calls)
"""
import logging
import time
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from app.config import Settings
from app.graph.build import build_graph
from app.llm import make_chat_model
from app.retrieval.embeddings import make_embedder
from app.retrieval.search import INDEX_CACHE


class Collector(logging.Handler):
    """Keep (seconds since start, message) for every graph log line."""

    def __init__(self) -> None:
        super().__init__()
        self.t0, self.rows = time.perf_counter(), []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name in ("graph", "app.graph.nodes"):
            self.rows.append((time.perf_counter() - self.t0, record.getMessage()))


def run_case(graph, title: str, messages: list, mode: str = "hybrid") -> list[str]:
    """Run one question and return readable evidence lines."""
    collector = Collector()
    for name in ("graph", "app.graph.nodes"):
        logging.getLogger(name).setLevel(logging.INFO)
        logging.getLogger(name).addHandler(collector)
    out = graph.invoke({"messages": messages, "search_mode": mode, "top_k": 5})
    for name in ("graph", "app.graph.nodes"):
        logging.getLogger(name).removeHandler(collector)
    lines = [f"=== {title}", f"question: {messages[-1].content!r}  (history messages: {len(messages) - 1}, mode: {mode})"]
    plan = out["plan"]
    lines.append(f"plan: intent={plan.intent} standalone_query={plan.standalone_query!r} filters={plan.filters.model_dump()} "
                 f"needs_clarification={plan.needs_clarification} clarification_question={plan.clarification_question!r}")
    lines.append(f"status={out['status']} ranking_stage={out['ranking_stage']!r} rerank_note={out['rerank_note']}")
    lines.append("trace (seconds since run start):")
    lines += [f"  +{t:6.3f}s {m}" for t, m in collector.rows if "event=" in m or "planning failed" in m]
    ev = {m.split()[0] + " " + m.split()[1]: t for t, m in collector.rows if "event=" in m}
    if "node=lexical_node event=start" in ev:
        l0, l1, s0, s1 = (ev[f"node={n} event={e}"] for n, e in (("lexical_node", "start"), ("lexical_node", "end"), ("semantic_node", "start"), ("semantic_node", "end")))
        f0 = ev["node=fuse_node event=start"]
        lines.append(f"overlap: lexical {l0:.3f}-{l1:.3f}s, semantic {s0:.3f}-{s1:.3f}s -> started together (within {abs(l0 - s0) * 1000:.0f} ms): {abs(l0 - s0) < 0.05}; "
                     f"semantic started before lexical ended: {s0 < l1}")
        lines.append(f"join: fuse started at {f0:.3f}s, after both branches ended ({max(l1, s1):.3f}s): {f0 >= max(l1, s1)}; "
                     f"fuse start events: {sum('node=fuse_node event=start' in m for _, m in collector.rows)}")
    if out["fused"]:
        lines.append("order BEFORE rerank (fused RRF): " + ", ".join(c.record.chunk_id for c in out["fused"][:8]))
        lines.append("order AFTER rerank (final top 5):  " + ", ".join(f"{c.record.chunk_id}[{c.score:.0f}]" for c in out["evidence"]))
    return lines + [""]


def main() -> None:
    """Run four cases and export the graph picture."""
    settings = Settings()
    graph = build_graph(settings, lambda: INDEX_CACHE.get(settings), make_embedder(settings), make_chat_model(settings))
    lines = ["AT-05 graph trace (real models, real index)\n"]
    lines += run_case(graph, "1. normal question, hybrid (parallel branches, join, rerank)",
                      [HumanMessage("Do I need a permit to import or sell a drone in Dubai?")])
    lines += run_case(graph, "2. follow-up using history (planner must rewrite it)",
                      [HumanMessage("What is the departure fee at Dubai airports?"),
                       AIMessage("The departure fee is AED 75 per passenger."), HumanMessage("Who is exempt from it?")])
    lines += run_case(graph, "3. out-of-scope question", [HumanMessage("What is a good recipe for pasta carbonara?")])
    lines += run_case(graph, "4. ambiguous question", [HumanMessage("What is the fine?")])
    text = "\n".join(lines)
    print(text)
    Path("evidence/AT-05_trace.txt").write_text(text + "\n", encoding="utf-8")
    Path("evidence/graph.mmd").write_text(graph.get_graph(xray=True).draw_mermaid(), encoding="utf-8")


if __name__ == "__main__":
    main()

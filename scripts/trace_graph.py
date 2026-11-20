"""AT-05, AT-06, AT-07 evidence: run the real graph (real models).

Records a timed node trace, the plan, the order before/after reranking, answers with citations, abstentions, and how
often the model's citations fail verification.  Usage: python -m scripts.trace_graph   (makes real model calls)
"""
import json
import logging
import re
import time
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from app.chat import make_checkpointer, run_chat
from app.config import Settings
from app.graph.build import build_graph
from app.llm import make_chat_model
from app.retrieval.embeddings import make_embedder
from app.retrieval.search import INDEX_CACHE
from app.schemas.chat import ChatRequest

LOGGERS = ("graph", "app.graph.nodes", "app.graph.answer")


class Collector(logging.Handler):
    """Keep (seconds since start, message) for every graph log line."""

    def __init__(self) -> None:
        super().__init__()
        self.t0, self.rows = time.perf_counter(), []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name in LOGGERS:
            self.rows.append((time.perf_counter() - self.t0, record.getMessage()))


def invoke_with_logs(graph, messages: list, mode: str = "hybrid") -> tuple[dict, Collector]:
    """Run one question while collecting the graph's log lines."""
    collector = Collector()
    for name in LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)
        logging.getLogger(name).addHandler(collector)
    try:
        out = graph.invoke({"messages": messages, "search_mode": mode, "top_k": 5})
    finally:
        for name in LOGGERS:
            logging.getLogger(name).removeHandler(collector)
    return out, collector


def run_case(graph, title: str, messages: list, mode: str = "hybrid") -> list[str]:
    """Run one question and return readable evidence lines."""
    out, collector = invoke_with_logs(graph, messages, mode)
    lines = [f"=== {title}", f"question: {messages[-1].content!r}  (history messages: {len(messages) - 1}, mode: {mode})"]
    plan = out["plan"]
    lines.append(f"plan: intent={plan.intent} standalone_query={plan.standalone_query!r} filters={plan.filters.model_dump()} "
                 f"needs_clarification={plan.needs_clarification} clarification_question={plan.clarification_question!r}")
    lines.append(f"status={out['status']} ranking_stage={out['ranking_stage']!r} rerank_note={out['rerank_note']}")
    if out["answer"]:
        lines.append("ANSWER:")
        lines += ["  | " + line for line in out["answer"].splitlines()]
    for i, c in enumerate(out["citations"], 1):
        lines.append(f"  citation [{i}]: document_id={c.document_id} chunk_id={c.chunk_id} locator_type={c.locator_type} locator={c.locator!r}")
        lines.append(f"               title={c.title!r}")
        lines.append(f"               source_url={c.source_url[:70]}...")
    verified = [m for _, m in collector.rows if m.startswith("answer verified")]
    if verified:
        lines.append("verification: " + verified[0].replace("answer verified ", ""))
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


def verification_totals(graph, questions: list[dict]) -> list[str]:
    """Run the evaluation questions end to end and count how many model statements verification kept or dropped."""
    totals = {"statements": 0, "kept": 0, "unknown_id": 0, "quote_mismatch": 0}
    statuses: dict[str, int] = {}
    for q in questions:
        out, collector = invoke_with_logs(graph, [HumanMessage(q["question"])])
        statuses[out["status"]] = statuses.get(out["status"], 0) + 1
        for _, message in collector.rows:
            if message.startswith("answer verified"):
                for key, value in re.findall(r"(\w+)=(\d+)", message):
                    totals[key] += int(value)
    return [f"statuses over {len(questions)} evaluation questions: {statuses}",
            f"model statements: {totals['statements']} | kept after verification: {totals['kept']} | "
            f"dropped, chunk id not among the evidence: {totals['unknown_id']} | dropped, quote not found in that chunk: {totals['quote_mismatch']}"]


def answer_cases(graph) -> list[str]:
    """AT-06 (supported questions) and AT-07 (abstention and scope) with real models."""
    lines = ["AT-06 / AT-07 answers (real models, real index)\n"]
    lines += run_case(graph, "AT-06a supported question, expect a cited answer",
                      [HumanMessage("How much is the departure fee for passengers leaving through Dubai airports, and who is exempt from it?")])
    lines += run_case(graph, "AT-06b supported question about a permit", [HumanMessage("Do I need a permit to import or sell a drone in Dubai?")])
    lines += run_case(graph, "AT-06c question whose best source is Not in Force (status must be disclosed)",
                      [HumanMessage("Can a driver carry passengers in a vehicle that the licensing authority has not licensed to transport passengers?")])
    lines += run_case(graph, "AT-07a in-scope question the documents do not cover, expect insufficient_evidence",
                      [HumanMessage("What is the fine for parking a camel outside a mosque in Dubai?")])
    lines += run_case(graph, "AT-07b unrelated question, expect out_of_scope", [HumanMessage("What is a good recipe for pasta carbonara?")])
    questions = json.loads(Path("data/eval_questions.json").read_text(encoding="utf-8"))
    lines += ["=== citation verification across the 10 evaluation questions"] + verification_totals(graph, questions)
    return lines


def trace_cases(graph) -> list[str]:
    """AT-05: routing, parallel branches, join and rerank."""
    lines = ["AT-05 graph trace (real models, real index)\n"]
    lines += run_case(graph, "1. normal question, hybrid (parallel branches, join, rerank)", [HumanMessage("Do I need a permit to import or sell a drone in Dubai?")])
    lines += run_case(graph, "2. follow-up using history (planner must rewrite it)",
                      [HumanMessage("What is the departure fee at Dubai airports?"), AIMessage("The departure fee is AED 75 per passenger."),
                       HumanMessage("Who is exempt from it?")])
    lines += run_case(graph, "3. out-of-scope question", [HumanMessage("What is a good recipe for pasta carbonara?")])
    lines += run_case(graph, "4. ambiguous question", [HumanMessage("What is the fine?")])
    return lines


def memory_cases(settings: Settings) -> list[str]:
    """AT-08: follow-up continuity, thread isolation, and memory after a simulated restart (real models, demo checkpoint file)."""
    demo_db = Path("data/checkpoints_demo.sqlite")  # separate from the real conversation database
    demo_db.unlink(missing_ok=True)

    def new_graph():
        return build_graph(settings, lambda: INDEX_CACHE.get(settings), make_embedder(settings), make_chat_model(settings),
                           checkpointer=make_checkpointer(str(demo_db)))

    def ask(graph, thread: str, message: str) -> list[str]:
        reply = run_chat(settings, ChatRequest(message=message, thread_id=thread, search_mode="hybrid"), graph)
        values = graph.get_state({"configurable": {"thread_id": thread}}).values
        text = (reply.answer or "").replace("\n", " ")[:170]
        return [f"[{thread}] user: {message!r}",
                f"    planner's standalone_query: {values['standalone_query']!r}",
                f"    status={reply.status} citations={len(reply.citations)} request_id={reply.request_id}",
                f"    answer: {text}...", ""]

    def saved(graph, thread: str) -> str:
        messages = graph.get_state({"configurable": {"thread_id": thread}}).values.get("messages", [])
        return f"[{thread}] saved messages: {len(messages)} -> " + " | ".join(f"{m.type}:{str(m.content)[:45]!r}" for m in messages)

    graph = new_graph()
    lines = ["AT-08 memory and isolation (real models; checkpoint file: data/checkpoints_demo.sqlite)\n", "--- thread A: a question, then a follow-up that only makes sense with the history"]
    lines += ask(graph, "demo-thread-a", "How much is the departure fee for passengers leaving through Dubai airports?")
    lines += ask(graph, "demo-thread-a", "Who is exempt from it?")
    lines += ["--- thread B: the SAME follow-up words, but this thread has no history"]
    lines += ask(graph, "demo-thread-b", "Who is exempt from it?")
    lines += ["--- saved state per thread", saved(graph, "demo-thread-a"), saved(graph, "demo-thread-b"), ""]
    lines += ["--- simulated restart: a brand-new graph object and a brand-new connection to the same file, then thread A continues"]
    restarted = new_graph()
    lines += [saved(restarted, "demo-thread-a")]
    lines += ask(restarted, "demo-thread-a", "What are the airlines responsible for?")
    lines += [saved(restarted, "demo-thread-a")]
    return lines


def main() -> None:
    """Write the AT-06/07 answer evidence, the AT-08 memory evidence, the AT-05 trace, and export the graph picture."""
    settings = Settings()
    memory = "\n".join(memory_cases(settings))
    print(memory)
    Path("evidence/AT-08_memory.txt").write_text(memory + "\n", encoding="utf-8")
    graph = build_graph(settings, lambda: INDEX_CACHE.get(settings), make_embedder(settings), make_chat_model(settings))
    answers = "\n".join(answer_cases(graph))
    print(answers)
    Path("evidence/AT-06_07_answers.txt").write_text(answers + "\n", encoding="utf-8")
    Path("evidence/AT-05_trace.txt").write_text("\n".join(trace_cases(graph)) + "\n", encoding="utf-8")
    Path("evidence/graph.mmd").write_text(graph.get_graph(xray=True).draw_mermaid(), encoding="utf-8")


if __name__ == "__main__":
    main()

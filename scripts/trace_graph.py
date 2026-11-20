"""AT-05, AT-06, AT-07 evidence: run the real graph (real models).

Records a timed node trace, the plan, the order before/after reranking, answers with citations, abstentions, and how
often the model's citations fail verification.  Usage: python -m scripts.trace_graph   (makes real model calls)
"""
import json
import logging
import re
import time
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.chat import make_checkpointer, pending_interrupts, resume_chat, run_chat
from app.config import Settings
from app.graph.build import build_graph
from app.graph.excerpt import make_excerpt_agent
from app.llm import make_chat_model
from app.retrieval.embeddings import make_embedder
from app.retrieval.search import INDEX_CACHE
from app.errors import InvalidResumeError
from app.schemas.chat import ChatRequest, ResumeRequest

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
        out = graph.invoke({"messages": messages, "search_mode": mode, "top_k": 5}, {"configurable": {"thread_id": uuid.uuid4().hex}})
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
        status = out.get("status", "needs_clarification")  # a paused run has no final status
        statuses[status] = statuses.get(status, 0) + 1
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


def interrupt_cases(settings: Settings) -> list[str]:
    """AT-09/AT-11: a real pause, a simulated restart, invalid resumes refused, then the resume (real models, demo checkpoint file)."""
    demo_db, thread = Path("data/checkpoints_demo.sqlite"), "demo-interrupt"

    def new_graph():
        return build_graph(settings, lambda: INDEX_CACHE.get(settings), make_embedder(settings), make_chat_model(settings),
                           checkpointer=make_checkpointer(str(demo_db)))

    def waiting(graph) -> str:
        state = graph.get_state({"configurable": {"thread_id": thread}})
        pending = [(i.id, i.value) for i in pending_interrupts(graph, thread)]
        return f"saved state: next={state.next} pending_interrupts={pending} saved_messages={len(state.values.get('messages', []))}"

    collector = Collector()
    for name in LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)
        logging.getLogger(name).addHandler(collector)
    lines = ["AT-09 interrupt and restart, AT-11 invalid resumes (real models; checkpoint file: data/checkpoints_demo.sqlite)\n"]
    graph = new_graph()
    paused = run_chat(settings, ChatRequest(message="What is the fine?", thread_id=thread), graph)
    lines += ["--- 1. ambiguous question 'What is the fine?' on a new thread",
              f"status={paused.status} thread_id={paused.thread_id} request_id={paused.request_id}",
              f"clarification: interrupt_id={paused.clarification.interrupt_id} question={paused.clarification.question!r}", waiting(graph), ""]
    lines += ["--- 2. simulated restart: a brand-new graph and a brand-new connection to the same file", waiting(new_graph()), ""]
    restarted = new_graph()
    lines.append("--- 3. invalid resumes are refused (AT-11)")
    for label, request in (("unknown thread", ResumeRequest(thread_id="never-seen", interrupt_id="x", message="hi")),
                           ("wrong interrupt id", ResumeRequest(thread_id=thread, interrupt_id="not-the-right-id", message="hi"))):
        try:
            resume_chat(settings, request, restarted)
            lines.append(f"{label}: UNEXPECTEDLY ACCEPTED")
        except InvalidResumeError as exc:
            lines.append(f"{label}: refused (HTTP 409): {exc}")
    try:
        run_chat(settings, ChatRequest(message="a new message", thread_id=thread), restarted)
        lines.append("new message on the paused thread: UNEXPECTEDLY ACCEPTED")
    except InvalidResumeError as exc:
        lines.append(f"new message on the paused thread: refused (HTTP 409): {exc}")
    lines += [waiting(restarted) + "   <- still waiting, untouched by the refused requests", ""]
    answer = "I mean the fees for passengers leaving through Dubai airports"
    done = resume_chat(settings, ResumeRequest(thread_id=thread, interrupt_id=paused.clarification.interrupt_id, message=answer), restarted)
    values = restarted.get_state({"configurable": {"thread_id": thread}}).values
    lines += [f"--- 4. resume on the restarted service with the SAME thread_id and the interrupt id from step 1: {answer!r}",
              f"status={done.status} thread_id={done.thread_id} citations={len(done.citations)} request_id={done.request_id}",
              f"planner's standalone_query after the clarification: {values['standalone_query']!r}",
              f"clarification_attempts={values['clarification_attempts']}", f"answer: {(done.answer or '').splitlines()[0][:200]}", waiting(restarted), ""]
    try:
        resume_chat(settings, ResumeRequest(thread_id=thread, interrupt_id=paused.clarification.interrupt_id, message="again"), restarted)
        lines.append("--- 5. resuming the finished thread again: UNEXPECTEDLY ACCEPTED")
    except InvalidResumeError as exc:
        lines.append(f"--- 5. resuming the finished thread again is refused (HTTP 409): {exc}")
    starts = [f"+{t:6.3f}s {m.split(' request_id')[0]}" for t, m in collector.rows if m.startswith("node=clarify event=")]
    lines += ["", "--- clarify node log lines (it STARTS twice but ENDS once: on resume the node runs again from its first line)"] + starts
    for name in LOGGERS:
        logging.getLogger(name).removeHandler(collector)
    return lines


def tool_cases(settings: Settings) -> list[str]:
    """AT-10: a model-issued tool call with validated arguments, its result, the middleware log lines, a controlled failure and the bounds."""
    llm, index = make_chat_model(settings), INDEX_CACHE.get(settings)
    graph = build_graph(settings, lambda: INDEX_CACHE.get(settings), make_embedder(settings), llm, checkpointer=InMemorySaver())
    collector = Collector()
    for name in LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)
        logging.getLogger(name).addHandler(collector)

    def log_lines() -> list[str]:
        return [f"  +{t:6.3f}s {m.split(' request_id')[0]}" for t, m in collector.rows
                if "middleware=" in m or m.startswith("excerpt agent") or "node=excerpt" in m]

    def graph_case(title: str, question: str) -> list[str]:
        collector.rows.clear()
        out = graph.invoke({"messages": [HumanMessage(question)], "search_mode": "hybrid", "top_k": 5}, {"configurable": {"thread_id": uuid.uuid4().hex}})
        tool_ids = {c.record.chunk_id for c in out["evidence"] if c.stage == "tool_excerpt"}
        cited = {c.chunk_id for c in out["citations"]}
        return [f"=== {title}", f"question: {question!r}", f"status={out['status']} evidence stages: {[c.stage for c in out['evidence']]}",
                f"chunks added by the tool: {sorted(tool_ids)}", f"citations: {len(out['citations'])}; citations that point to a tool-fetched chunk: {sorted(cited & tool_ids)}",
                "log lines (seconds since start):"] + log_lines() + [""]

    def agent_case(title: str, text: str) -> list[str]:
        collector.rows.clear()
        out = make_excerpt_agent(llm, lambda: index).invoke({"messages": [HumanMessage(text)]})
        lines = [f"=== {title}", f"instruction to the agent: {text!r}", "messages:"]
        for m in out["messages"][1:]:
            calls = [(c["name"], c["args"]) for c in getattr(m, "tool_calls", None) or []]
            lines.append(f"  {m.type:5s} status={getattr(m, 'status', '-')} tool_calls={calls} content={str(m.content)[:130]!r}".replace("\n", " "))
        return lines + ["log lines (seconds since start):"] + log_lines() + [""]

    doc = index.records[0].doc_id
    lines = ["AT-10 tool call and middleware (real models, real index)\n",
             "Middleware placement: inside the agent created by create_agent (node 'excerpt'): monitor_tool_call wraps every tool call; "
             "ModelCallLimitMiddleware(run_limit=3) and ToolCallLimitMiddleware(run_limit=2) bound the loop. FastAPI HTTP middleware is not used for this.\n"]
    lines += graph_case("1. ordinary question: the user did not ask about pages, so the agent step is skipped (no extra model call)",
                        "Do I need a permit to import or sell a drone in Dubai?")
    lines += graph_case("2. the user asks for another page: the MODEL chooses to call get_document_excerpt",
                        "How much is the departure fee for passengers leaving through Dubai airports? Please also read the next page of the most relevant document.")
    lines += agent_case("3. controlled tool failure: the model asks for a document that is not in the corpus",
                        "Use get_document_excerpt to read page 1 of document dlp-99999 and tell me what it says.")
    lines += agent_case("4. bounded calls: the model is asked for five pages but at most 2 tool calls per run are allowed",
                        f"Use get_document_excerpt to read pages 1, 2, 3, 4 and 5 of document {doc}, one call per page.")
    for name in LOGGERS:
        logging.getLogger(name).removeHandler(collector)
    return lines


def main() -> None:
    """Write the AT-06/07 answer, AT-08 memory and AT-09 interrupt evidence, the AT-05 trace, and export the graph picture."""
    settings = Settings()
    memory = "\n".join(memory_cases(settings))
    print(memory)
    Path("evidence/AT-08_memory.txt").write_text(memory + "\n", encoding="utf-8")
    interrupts = "\n".join(interrupt_cases(settings))
    print(interrupts)
    Path("evidence/AT-09_interrupt.txt").write_text(interrupts + "\n", encoding="utf-8")
    tools = "\n".join(tool_cases(settings))
    print(tools)
    Path("evidence/AT-10_tool_middleware.txt").write_text(tools + "\n", encoding="utf-8")
    graph = build_graph(settings, lambda: INDEX_CACHE.get(settings), make_embedder(settings), make_chat_model(settings),
                        checkpointer=InMemorySaver())
    answers = "\n".join(answer_cases(graph))
    print(answers)
    Path("evidence/AT-06_07_answers.txt").write_text(answers + "\n", encoding="utf-8")
    Path("evidence/AT-05_trace.txt").write_text("\n".join(trace_cases(graph)) + "\n", encoding="utf-8")
    Path("evidence/graph.mmd").write_text(graph.get_graph(xray=True).draw_mermaid(), encoding="utf-8")


if __name__ == "__main__":
    main()

"""Tests for the LangGraph workflow. Models are FAKES; documents are FAKE records from tests.test_search."""
import logging
import re
import time

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.config import Settings
from app.errors import ModelNotConfiguredError
from app.graph import retrieval as graph_retrieval
from app.graph.build import build_graph
from app.graph.nodes import SCOPE_MESSAGE, history_block, route_after_plan
from app.retrieval.filters import SearchFilters
from app.schemas.answer import AnswerDraft, Statement
from app.schemas.plan import PlanFilters, QueryPlan
from app.schemas.search import RerankResult, RerankScore
from tests.test_search import INDEX, FakeEmbedder

TEXT_BY_ID = {r.chunk_id: r.text for r in INDEX.records}

SETTINGS = Settings(_env_file=None, retrieval_candidates=5)


def plan(intent="legal_question", query="toll fine parking", clarify=False, question=None, year=None, doc_type=None) -> QueryPlan:
    """Build a FAKE query plan."""
    return QueryPlan(intent=intent, standalone_query=query, filters=PlanFilters(year=year, doc_type=doc_type),
                     needs_clarification=clarify, clarification_question=question)


class GraphFakeLLM:
    """FAKE chat model: returns a preset QueryPlan for planning, and prefers LAST excerpt when reranking."""

    def __init__(self, plan_result: QueryPlan | None = None, plan_error: Exception | None = None, insufficient: bool = False,
                 tool_call: dict | None = None) -> None:
        self.plan_result, self.plan_error, self.rerank_calls = plan_result or plan(), plan_error, 0
        self.insufficient, self.answer_calls = insufficient, 0
        self.tool_call, self.agent_calls = tool_call, 0  # tool_call: arguments the FAKE agent turn passes to get_document_excerpt

    def bind_tools(self, tools, **kwargs):
        """create_agent asks the model to know its tools; the fake ignores them."""
        return self

    def invoke(self, messages, **kwargs):
        """FAKE agent turn: call the scripted tool once (if any), then say done."""
        self.agent_calls += 1
        if self.tool_call and not any(getattr(m, "type", "") == "tool" for m in messages):
            return AIMessage(content="", tool_calls=[{"name": "get_document_excerpt", "args": self.tool_call, "id": "call-1"}])
        return AIMessage("done")

    def answer_draft(self, prompt: str) -> AnswerDraft:
        """FAKE answer: cites the first excerpt it was shown, quoting its first words (a valid, verifiable citation)."""
        if self.insufficient:
            return AnswerDraft(evidence_is_sufficient=False, statements=[])
        chunk_id = re.search(r'chunk_id="([^"]+)"', prompt).group(1)
        return AnswerDraft(evidence_is_sufficient=True,
                           statements=[Statement(text="FAKE statement", chunk_id=chunk_id, quote=TEXT_BY_ID[chunk_id][:20])])

    def with_structured_output(self, schema):
        outer = self

        class Runnable:
            def invoke(self, messages):
                if schema is QueryPlan:
                    if outer.plan_error:
                        raise outer.plan_error
                    return outer.plan_result
                if schema is AnswerDraft:
                    outer.answer_calls += 1
                    return outer.answer_draft(messages[1][1])
                outer.rerank_calls += 1
                n = messages[1][1].count("<excerpt id=")
                return RerankResult(scores=[RerankScore(candidate=i, relevance=i) for i in range(1, n + 1)])

        return Runnable()


def run(llm: GraphFakeLLM, embedder=FakeEmbedder(), **state):
    """Build the graph with fakes and run one question."""
    graph = build_graph(SETTINGS, lambda: INDEX, embedder, llm)
    state.setdefault("messages", [HumanMessage("toll fine parking?")])
    state.setdefault("search_mode", "hybrid")
    state.setdefault("top_k", 3)
    return graph.invoke(state)


def node_events(caplog) -> list[str]:
    """Return 'node=<name> event=<start|end>' entries from the graph logger, in order."""
    return [" ".join(r.getMessage().split()[:2]) for r in caplog.records if r.name == "graph"]


def test_normal_question_goes_through_hybrid_retrieval_and_reranking(caplog) -> None:
    """7.1: understand -> retrieve (lexical || semantic, join, fuse, rerank) -> answer."""
    with caplog.at_level(logging.INFO, logger="graph"):
        out = run(GraphFakeLLM())
    assert out["status"] == "answered" and out["ranking_stage"] == "reranked" and len(out["evidence"]) == 3
    assert out["standalone_query"] == "toll fine parking" and len(out["fused"]) == 5
    events = node_events(caplog)
    for name in ("start_turn", "plan_query", "lexical_node", "semantic_node", "fuse_node", "rerank_node", "answer"):
        assert f"node={name} event=end" in events


def test_out_of_scope_question_gets_the_scope_message_and_skips_retrieval(caplog) -> None:
    """AT-07 routing: no search, no model call for retrieval, no invented answer."""
    with caplog.at_level(logging.INFO, logger="graph"):
        out = run(GraphFakeLLM(plan("out_of_scope", "best pasta recipe")))
    assert out["status"] == "out_of_scope" and out["answer"] == SCOPE_MESSAGE and out["evidence"] == []
    events = node_events(caplog)
    assert "node=scope_response event=end" in events
    assert not any(e.startswith(("node=lexical", "node=semantic", "node=fuse", "node=rerank")) for e in events)


def test_ambiguous_question_is_clarified_at_most_twice() -> None:
    """7.2: clarify while fewer than 2 attempts are used; after that, search the question as written."""
    ambiguous = plan(clarify=True, question="Which law do you mean?")
    assert route_after_plan({"plan": ambiguous, "clarification_attempts": 0}) == "clarify"
    assert route_after_plan({"plan": ambiguous, "clarification_attempts": 1}) == "clarify"
    assert route_after_plan({"plan": ambiguous, "clarification_attempts": 2}) == "retrieval"


def test_lexical_and_semantic_modes_take_a_single_branch() -> None:
    """RAG-01: route by mode; lexical never touches the embedder, neither mode reranks."""
    class CountingEmbedder(FakeEmbedder):
        calls = 0

        def embed_query(self, text):
            CountingEmbedder.calls += 1
            return super().embed_query(text)

    llm = GraphFakeLLM()
    lexical = run(llm, CountingEmbedder(), search_mode="lexical")
    assert lexical["ranking_stage"] == "lexical" and CountingEmbedder.calls == 0
    semantic = run(llm, CountingEmbedder(), search_mode="semantic")
    assert semantic["ranking_stage"] == "semantic" and CountingEmbedder.calls == 1 and llm.rerank_calls == 0


def test_stale_values_from_a_previous_question_are_reset_but_messages_persist() -> None:
    """7.2: start_turn wipes per-question fields; the conversation (messages) is kept and extended."""
    old = [HumanMessage("earlier question"), AIMessage("earlier answer"), HumanMessage("what is the fine?")]
    out = run(GraphFakeLLM(plan("out_of_scope", "x")), messages=old, evidence=["STALE"], answer="STALE", citations=["STALE"], fused=["STALE"],
              lexical_candidates=["STALE"], clarification_attempts=2)
    assert out["evidence"] == [] and out["fused"] == [] and out["lexical_candidates"] == [] and out["clarification_attempts"] == 0
    assert out["citations"] == []
    assert out["answer"] == SCOPE_MESSAGE
    assert [m.content for m in out["messages"]][:3] == ["earlier question", "earlier answer", "what is the fine?"]
    assert out["messages"][-1].content == SCOPE_MESSAGE


def test_retrieval_uses_the_standalone_query_not_the_raw_message(monkeypatch) -> None:
    """A follow-up like 'and the penalty?' is searched using the planner's rewritten, self-contained query."""
    seen = []
    real = graph_retrieval.lexical_search
    monkeypatch.setattr(graph_retrieval, "lexical_search", lambda index, q, f, k: (seen.append(q), real(index, q, f, k))[1])
    run(GraphFakeLLM(plan(query="parking fine")), messages=[HumanMessage("and the penalty?")], search_mode="lexical")
    assert seen == ["parking fine"]


def test_request_filters_win_over_planner_filters_and_planner_fills_the_gaps() -> None:
    """The caller's filters are never overridden; filters the user stated in words are added when none were sent."""
    from_plan = run(GraphFakeLLM(plan(query="toll fine parking licence", year=2023)), search_mode="lexical")
    assert from_plan["effective_filters"].year == 2023 and all(c.record.year == 2023 for c in from_plan["evidence"])
    from_request = run(GraphFakeLLM(plan(query="toll fine parking licence", year=2023)), search_mode="lexical", filters=SearchFilters(year=2020))
    assert from_request["effective_filters"].year == 2020 and all(c.record.year == 2020 for c in from_request["evidence"])


def test_planner_failure_falls_back_to_searching_the_question_as_written() -> None:
    """A model error while planning must not stop the question."""
    out = run(GraphFakeLLM(plan_error=TimeoutError("FAKE")), messages=[HumanMessage("toll parking")], search_mode="lexical")
    assert out["status"] == "answered" and out["standalone_query"] == "toll parking"


def test_semantic_mode_without_an_embedder_raises_a_controlled_error() -> None:
    """Missing credentials give ModelNotConfiguredError (the API maps it to 503), not a crash deep inside."""
    with pytest.raises(ModelNotConfiguredError):
        run(GraphFakeLLM(), embedder=None, search_mode="semantic")


def test_hybrid_branches_run_in_parallel_and_the_join_runs_once_after_both(monkeypatch, caplog) -> None:
    """RAG-02/AT-05: two 0.4 s branches take about 0.4 s in total, and fuse starts once, after both ended."""
    def slow(result):
        def fn(*args, **kwargs):
            time.sleep(0.4)
            return result
        return fn

    real = graph_retrieval.lexical_search(INDEX, "toll", SearchFilters(), 5)
    monkeypatch.setattr(graph_retrieval, "lexical_search", slow(real))
    monkeypatch.setattr(graph_retrieval, "checked_semantic_search", slow(real))
    with caplog.at_level(logging.INFO, logger="graph"):
        started = time.perf_counter()
        out = run(GraphFakeLLM())
        total = time.perf_counter() - started
    assert total < 0.75  # sequential would take at least 0.8 s
    events = node_events(caplog)
    assert events.count("node=fuse_node event=start") == 1 and events.count("node=answer event=start") == 1
    fuse_start = events.index("node=fuse_node event=start")
    assert events.index("node=lexical_node event=end") < fuse_start and events.index("node=semantic_node event=end") < fuse_start
    assert out["status"] == "answered"


def test_each_parallel_branch_writes_only_its_own_key() -> None:
    """7.2: separate output keys, so no reducer or conflict is needed."""
    out = run(GraphFakeLLM())
    assert out["lexical_candidates"] and out["semantic_candidates"]
    assert {c.stage for c in out["lexical_candidates"]} == {"lexical"} and {c.stage for c in out["semantic_candidates"]} == {"semantic"}


def test_query_plan_rejects_inconsistent_combinations() -> None:
    """Pydantic-validated plan: out-of-scope cannot need clarification, and a clarification needs its question."""
    with pytest.raises(ValueError):
        plan("out_of_scope", "x", clarify=True, question="?")
    with pytest.raises(ValueError):
        plan(clarify=True, question="  ")


def test_history_shown_to_the_planner_is_bounded_and_labelled() -> None:
    """The planner prompt contains at most the last 6 earlier messages, each truncated."""
    messages = [HumanMessage(f"q{i} " + "x" * 2000) if i % 2 == 0 else AIMessage(f"a{i}") for i in range(10)] + [HumanMessage("now")]
    lines = history_block(messages).splitlines()
    assert len(lines) == 6 and all(len(line) <= 620 for line in lines) and lines[-1] == "Assistant: a9"

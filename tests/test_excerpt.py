"""Tests for the excerpt agent step: tool arguments, corpus boundary, model-chosen tool call, middleware, bounds.

Models are FAKES (they only script a tool call); documents are FAKE records from tests.test_search.
"""
import logging

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from app.graph.excerpt import ExcerptArgs, find_excerpt_chunks, make_excerpt_agent, read_more_evidence
from app.schemas.search import RankedChunk
from tests.test_graph import GraphFakeLLM, run
from app.retrieval.index import SearchIndex
from tests.test_search import INDEX, rec

METRO = next(r for r in INDEX.records if r.chunk_id == "metro")
EVIDENCE = [RankedChunk(record=METRO, rank=1, score=7.0, score_type="llm_relevance_0_10", stage="reranked")]
READ_P1 = {"document_id": "fake", "locator": "p. 1"}


ASKS_FOR_A_PAGE = "toll fine parking? please also read the next page"


def step(llm: GraphFakeLLM, question: str = ASKS_FOR_A_PAGE) -> dict:
    """Run the excerpt node on its own, with the real agent, middleware and tool, and a FAKE model."""
    agent = make_excerpt_agent(llm, lambda: INDEX)
    state = {"evidence": EVIDENCE, "standalone_query": "toll fine", "messages": [HumanMessage(question)]}
    return read_more_evidence(state, agent=agent, get_index=lambda: INDEX)


@pytest.mark.parametrize("args", [{"document_id": "dlp-1", "locator": "page one"}, {"document_id": "dlp-1", "locator": "p. 12345"},
                                  {"document_id": "../etc", "locator": "p. 1"}, {"document_id": "", "locator": "p. 1"}])
def test_tool_arguments_are_validated_before_the_tool_runs(args) -> None:
    """7.3: a bad locator or document id shape is rejected by the argument schema."""
    with pytest.raises(ValidationError):
        ExcerptArgs(**args)


def test_the_tool_reads_only_the_indexed_corpus() -> None:
    """7.3 corpus restriction: unknown documents and pages fail; a chunk of another category is never returned, even with a known id."""
    assert len(find_excerpt_chunks(INDEX, "fake", "p. 1")) == 2  # capped at MAX_CHUNKS_PER_READ
    outside = SearchIndex([rec("traffic-only", "toll toll outside the corpus", category="Traffic")])  # same doc id, other category
    with pytest.raises(ValueError, match="not a document in the indexed corpus"):
        find_excerpt_chunks(outside, "fake", "p. 1")
    with pytest.raises(ValueError, match="not a document in the indexed corpus"):
        find_excerpt_chunks(INDEX, "dlp-99999", "p. 1")
    with pytest.raises(ValueError, match="no stored text"):
        find_excerpt_chunks(INDEX, "fake", "p. 9")


def test_a_model_issued_tool_call_adds_the_chunks_it_received_to_the_evidence(caplog) -> None:
    """AT-10: the model (not our code) calls the tool; the hook logs it; the returned chunks join the evidence, labelled."""
    llm = GraphFakeLLM(tool_call=READ_P1)
    with caplog.at_level(logging.INFO, logger="graph"):
        out = step(llm)
    added = out["evidence"][1:]
    assert out["evidence"][0].record.chunk_id == "metro" and {c.record.chunk_id for c in added} == {"toll", "fine"}
    assert all(c.stage == "tool_excerpt" and c.score_type == "not_scored" for c in added)
    assert llm.agent_calls == 2  # one turn that asked for the tool, one turn that said done
    lines = [r.getMessage() for r in caplog.records if "middleware=monitor_tool_call" in r.getMessage()]
    assert "event=start tool=get_document_excerpt" in lines[0] and "event=end tool=get_document_excerpt status=success" in lines[1]


def test_a_failing_tool_call_is_controlled_and_the_evidence_is_unchanged(caplog) -> None:
    """AT-10 controlled failure: an unknown document becomes an error message for the model; nothing crashes or is added."""
    with caplog.at_level(logging.INFO, logger="graph"):
        out = step(GraphFakeLLM(tool_call={"document_id": "dlp-99999", "locator": "p. 1"}))
    assert out == {}
    assert any("event=failed tool=get_document_excerpt error=ValueError" in r.getMessage() for r in caplog.records)


def test_an_ordinary_question_skips_the_agent_step_entirely() -> None:
    """Measured cost control: without a page request in the user's message there is no extra model call."""
    llm = GraphFakeLLM(tool_call=READ_P1)
    assert step(llm, "toll fine parking?") == {} and llm.agent_calls == 0


def test_no_tool_call_means_no_change() -> None:
    """The model may decide the evidence is enough: the evidence stays as retrieved."""
    assert step(GraphFakeLLM()) == {}


def test_a_model_that_keeps_calling_the_tool_is_stopped_by_the_call_limits() -> None:
    """7.2 bounds: the middleware limits (3 model calls, 2 tool calls per run) end a loop the model would not end itself."""
    class Insatiable(GraphFakeLLM):
        def invoke(self, messages, **kwargs):
            self.agent_calls += 1
            return AIMessage(content="", tool_calls=[{"name": "get_document_excerpt", "args": READ_P1, "id": f"call-{self.agent_calls}"}])

    llm = Insatiable()
    step(llm)
    assert llm.agent_calls <= 3


def test_a_crashing_agent_does_not_stop_the_question(caplog) -> None:
    """The agent step is optional enrichment: if the model call fails, the retrieved evidence is used as it is."""
    class Broken(GraphFakeLLM):
        def invoke(self, messages, **kwargs):
            raise TimeoutError("model unreachable")

    with caplog.at_level(logging.WARNING, logger="graph"):
        assert step(Broken()) == {}
    assert any("excerpt agent failed error=TimeoutError" in r.getMessage() for r in caplog.records)


def test_the_graph_runs_the_excerpt_step_between_retrieval_and_the_answer(caplog) -> None:
    """7.1: the extra evidence reaches the answer node, which still verifies its citations against it."""
    with caplog.at_level(logging.INFO, logger="graph"):
        out = run(GraphFakeLLM(tool_call=READ_P1), messages=[HumanMessage(ASKS_FOR_A_PAGE)], search_mode="lexical", top_k=1)
    stages = {c.stage for c in out["evidence"]}
    assert "tool_excerpt" in stages and out["status"] == "answered"
    events = [" ".join(r.getMessage().split()[:2]) for r in caplog.records if r.name == "graph" and r.getMessage().startswith("node=")]
    assert events.index("node=excerpt event=end") < events.index("node=answer event=start")

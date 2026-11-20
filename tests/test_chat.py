"""Tests for POST /chat and the chat service: memory per thread, isolation, restart, busy threads, validation.

Models are FAKES; documents are FAKE records from tests.test_search; the checkpoint database lives in a temp folder.
"""
import logging
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.chat import make_checkpointer, run_chat, thread_lock
from app.config import Settings
from app.errors import IndexNotReadyError, ModelCallError, ModelNotConfiguredError, ThreadBusyError
from app.graph.build import build_graph
from app.graph.nodes import SCOPE_MESSAGE
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.plan import QueryPlan
from tests.test_graph import GraphFakeLLM, plan
from tests.test_search import INDEX, FakeEmbedder

SETTINGS = Settings(_env_file=None, retrieval_candidates=5)


class RecordingLLM(GraphFakeLLM):
    """FAKE chat model that also remembers every prompt the planner was given."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.plan_prompts: list[str] = []

    def with_structured_output(self, schema):
        inner, outer = super().with_structured_output(schema), self

        class Runnable:
            def invoke(self, messages):
                if schema is QueryPlan:
                    outer.plan_prompts.append(messages[1][1])
                return inner.invoke(messages)

        return Runnable()


def make_graph(path: Path, llm: GraphFakeLLM):
    """A graph with the real file-backed checkpointer and FAKE models."""
    return build_graph(SETTINGS, lambda: INDEX, FakeEmbedder(), llm, checkpointer=make_checkpointer(str(path)))


def chat(graph, message: str, thread_id: str | None = None, mode: str = "lexical") -> ChatResponse:
    """Send one message through the real chat service."""
    return run_chat(SETTINGS, ChatRequest(message=message, thread_id=thread_id, search_mode=mode), graph)


def test_new_thread_id_is_generated_and_every_response_field_is_present(tmp_path) -> None:
    """8.2: thread_id returned (generated when absent), status, answer, citations, clarification, request_id."""
    graph = make_graph(tmp_path / "c.sqlite", RecordingLLM())
    first = chat(graph, "toll fine parking?")
    assert len(first.thread_id) == 32 and first.status == "answered" and first.answer and first.citations
    assert first.clarification is None and first.request_id
    again = chat(graph, "toll fine parking?", thread_id=first.thread_id)
    assert again.thread_id == first.thread_id and again.request_id != first.request_id


def test_follow_up_on_the_same_thread_sees_the_earlier_conversation(tmp_path) -> None:
    """AT-08 continuity: the planner of the second question is shown the first question and answer."""
    llm = RecordingLLM()
    graph = make_graph(tmp_path / "c.sqlite", llm)
    chat(graph, "toll fine parking?", thread_id="thread-a")
    chat(graph, "and who is exempt?", thread_id="thread-a")
    assert "toll fine parking?" in llm.plan_prompts[1] and "(no earlier messages)" not in llm.plan_prompts[1]


def test_another_thread_does_not_see_the_conversation_of_thread_a(tmp_path) -> None:
    """AT-08 isolation: thread B starts with no history, and thread A is unchanged by B's questions."""
    llm = RecordingLLM()
    graph = make_graph(tmp_path / "c.sqlite", llm)
    chat(graph, "secret question about tolls", thread_id="thread-a")
    chat(graph, "who is exempt from it?", thread_id="thread-b")
    assert "secret question" not in llm.plan_prompts[1] and "(no earlier messages)" in llm.plan_prompts[1]
    assert len(graph.get_state({"configurable": {"thread_id": "thread-a"}}).values["messages"]) == 2
    assert len(graph.get_state({"configurable": {"thread_id": "thread-b"}}).values["messages"]) == 2


def test_memory_survives_a_restart(tmp_path) -> None:
    """AT-08/AT-09: a brand-new graph and a brand-new connection to the same file still know thread A."""
    path = tmp_path / "c.sqlite"
    chat(make_graph(path, RecordingLLM()), "remember this question about tolls", thread_id="thread-a")
    llm_after = RecordingLLM()
    chat(make_graph(path, llm_after), "and the exemptions?", thread_id="thread-a")  # 'restarted' process
    assert "remember this question about tolls" in llm_after.plan_prompts[0]


def test_per_question_fields_do_not_leak_into_the_next_question_on_the_same_thread(tmp_path) -> None:
    """start_turn: an out-of-scope second question must not reuse the first answer's citations or text."""
    path = tmp_path / "c.sqlite"
    first = chat(make_graph(path, RecordingLLM()), "toll fine parking?", thread_id="thread-a")
    assert first.citations
    second = chat(make_graph(path, RecordingLLM(plan("out_of_scope", "recipe"))), "pasta recipe?", thread_id="thread-a")
    assert second.status == "out_of_scope" and second.answer == SCOPE_MESSAGE and second.citations == []


def test_ambiguous_question_returns_the_clarification_to_ask(tmp_path) -> None:
    """The response carries the question the user must answer (the real pause comes in block 7)."""
    graph = make_graph(tmp_path / "c.sqlite", RecordingLLM(plan(clarify=True, question="Which law do you mean?")))
    reply = chat(graph, "what is the fine?")
    assert reply.status == "needs_clarification" and reply.clarification.question == "Which law do you mean?" and reply.citations == []


def test_a_second_request_on_a_busy_thread_is_refused_but_other_threads_are_not() -> None:
    """Same-thread serialization: one run per thread; different threads may run at the same time."""
    entered, release, results = threading.Event(), threading.Event(), []

    def hold_thread_a() -> None:
        with thread_lock("thread-a"):
            entered.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=hold_thread_a)
    worker.start()
    assert entered.wait(timeout=5)
    with pytest.raises(ThreadBusyError, match="thread-a"):
        with thread_lock("thread-a"):
            pass
    with thread_lock("thread-b"):  # a different thread is not blocked
        results.append("b ran")
    release.set()
    worker.join()
    with thread_lock("thread-a"):  # and the lock is free again afterwards
        results.append("a ran again")
    assert results == ["b ran", "a ran again"]


def test_node_log_lines_carry_request_id_and_thread_id(tmp_path, caplog) -> None:
    """8.3: node start/end are logged with the request id and the thread id."""
    graph = make_graph(tmp_path / "c.sqlite", RecordingLLM())
    with caplog.at_level(logging.INFO, logger="graph"):
        reply = chat(graph, "toll fine parking?", thread_id="thread-log")
    node_lines = [r.getMessage() for r in caplog.records if r.name == "graph"]
    assert node_lines and all(f"request_id={reply.request_id} thread_id=thread-log" in line for line in node_lines)


client = TestClient(main.app)


@pytest.mark.parametrize("body", [
    {"message": ""}, {"message": "   "}, {"message": "x" * 2001}, {}, {"message": "hi", "thread_id": "has spaces"},
    {"message": "hi", "thread_id": "a" * 65}, {"message": "hi", "thread_id": "bad/slash"}, {"message": "hi", "search_mode": "fuzzy"},
    {"message": "hi", "filters": {"year": 3000}}, {"message": "hi", "unknown_field": 1},
])
def test_chat_route_rejects_invalid_requests_with_422(body) -> None:
    """AT-11: empty message, over-length message, bad thread id, unsupported mode, invalid filters, unknown fields."""
    assert client.post("/chat", json=body).status_code == 422


def test_chat_route_returns_the_service_response_and_maps_errors(monkeypatch) -> None:
    """The route is thin: it returns the service's response, and known failures become controlled 409/503/502 responses."""
    ok = ChatResponse(thread_id="t1", status="out_of_scope", answer="x", citations=[], clarification=None, request_id="r1")
    monkeypatch.setattr(main, "run_chat", lambda settings, req: ok)
    assert client.post("/chat", json={"message": "hi"}).json()["thread_id"] == "t1"
    for error, status in ((ThreadBusyError("busy"), 409), (IndexNotReadyError("no index"), 503),
                          (ModelNotConfiguredError("no key"), 503), (ModelCallError("boom"), 502)):
        def raise_it(settings, req, error=error):
            raise error

        monkeypatch.setattr(main, "run_chat", raise_it)
        response = client.post("/chat", json={"message": "hi"})
        assert response.status_code == status and response.json()["detail"] == str(error)

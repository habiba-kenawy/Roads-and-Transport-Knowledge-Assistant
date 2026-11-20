"""Tests for POST /chat and the chat service: memory per thread, isolation, restart, busy threads, validation.

Models are FAKES; documents are FAKE records from tests.test_search; the checkpoint database lives in a temp folder.
"""
import logging
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.chat import make_checkpointer, resume_chat, run_chat, thread_lock
from app.config import Settings
from app.errors import IndexNotReadyError, InvalidResumeError, ModelCallError, ModelNotConfiguredError, ThreadBusyError
from app.graph.build import build_graph
from app.graph.nodes import SCOPE_MESSAGE
from app.schemas.chat import ChatRequest, ChatResponse, ResumeRequest
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


ASK = plan(clarify=True, question="Which law do you mean?")


def resume(graph, reply, answer: str = "the toll law", interrupt_id: str | None = None) -> ChatResponse:
    """Answer the pending clarification of `reply` through the real resume service."""
    return resume_chat(SETTINGS, ResumeRequest(thread_id=reply.thread_id, message=answer,
                                               interrupt_id=interrupt_id or reply.clarification.interrupt_id), graph)


def test_ambiguous_question_really_pauses_the_graph_and_returns_the_interrupt(tmp_path) -> None:
    """7.1/8.2: the response names the pending interrupt and its question; the saved state is waiting at 'clarify'."""
    graph = make_graph(tmp_path / "c.sqlite", RecordingLLM(ASK))
    reply = chat(graph, "what is the fine?", thread_id="t-ask")
    assert reply.status == "needs_clarification" and reply.answer is None and reply.citations == []
    assert reply.clarification.question == "Which law do you mean?" and reply.clarification.interrupt_id
    assert graph.get_state({"configurable": {"thread_id": "t-ask"}}).next == ("clarify",)


def test_resume_continues_the_same_thread_and_the_planner_sees_the_clarification(tmp_path) -> None:
    """7.1: the answer resumes the pending workflow (not a new unrelated run); the planner now sees question + reply."""
    llm = RecordingLLM(ASK)
    graph = make_graph(tmp_path / "c.sqlite", llm)
    paused = chat(graph, "what is the fine?", thread_id="t-res")
    llm.plan_result = plan()  # after the clarification the planner understands the question
    done = resume(graph, paused, "the toll law")
    assert done.thread_id == "t-res" and done.status == "answered" and done.citations and done.clarification is None
    assert "what is the fine?" in llm.plan_prompts[1] and "the toll law" in llm.plan_prompts[1]
    assert graph.get_state({"configurable": {"thread_id": "t-res"}}).next == ()


def test_pending_clarification_survives_a_restart_and_can_be_resumed(tmp_path) -> None:
    """AT-09: a brand-new graph on the same SQLite file resumes the thread that was paused before the 'restart'."""
    path = tmp_path / "c.sqlite"
    paused = chat(make_graph(path, RecordingLLM(ASK)), "what is the fine?", thread_id="t-restart")
    done = resume(make_graph(path, RecordingLLM()), paused)
    assert done.status == "answered" and done.thread_id == "t-restart"


def test_invalid_resumes_are_rejected_and_do_not_disturb_the_pending_clarification(tmp_path) -> None:
    """AT-11: unknown thread, finished thread and wrong interrupt id are refused; the right id still works afterwards."""
    llm = RecordingLLM(ASK)
    graph = make_graph(tmp_path / "c.sqlite", llm)
    paused = chat(graph, "what is the fine?", thread_id="t-bad")
    with pytest.raises(InvalidResumeError, match="no pending"):
        resume_chat(SETTINGS, ResumeRequest(thread_id="never-seen", interrupt_id="x", message="hi"), graph)
    with pytest.raises(InvalidResumeError, match="does not match"):
        resume(graph, paused, interrupt_id="not-the-right-id")
    llm.plan_result = plan()
    assert resume(graph, paused).status == "answered"
    with pytest.raises(InvalidResumeError, match="no pending"):  # the same resume a second time: nothing is waiting any more
        resume(graph, paused)


def test_a_new_message_on_a_paused_thread_is_refused(tmp_path) -> None:
    """A new /chat message must not silently abandon the question we asked."""
    graph = make_graph(tmp_path / "c.sqlite", RecordingLLM(ASK))
    chat(graph, "what is the fine?", thread_id="t-wait")
    with pytest.raises(InvalidResumeError, match="POST /chat/resume"):
        chat(graph, "something else", thread_id="t-wait")


def test_clarification_stops_after_two_attempts(tmp_path) -> None:
    """7.2: a planner that always wants clarification is asked twice; the third time the question is searched as written."""
    graph = make_graph(tmp_path / "c.sqlite", RecordingLLM(ASK))
    reply = chat(graph, "what is the fine?", thread_id="t-cap")
    reply = resume(graph, reply, "still vague")
    assert reply.status == "needs_clarification"  # second clarification
    reply = resume(graph, reply, "still vague again")
    assert reply.status == "answered"  # limit reached: no third question
    assert graph.get_state({"configurable": {"thread_id": "t-cap"}}).values["clarification_attempts"] == 2


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


@pytest.mark.parametrize("body", [
    {"thread_id": "t1", "interrupt_id": "abc", "message": ""}, {"thread_id": "t1", "message": "hi"}, {"interrupt_id": "abc", "message": "hi"},
    {"thread_id": "bad id", "interrupt_id": "abc", "message": "hi"}, {"thread_id": "t1", "interrupt_id": "abc", "message": "x" * 2001},
    {"thread_id": "t1", "interrupt_id": "abc", "message": "hi", "extra": 1},
])
def test_resume_route_rejects_invalid_requests_with_422(body) -> None:
    """AT-11: empty clarification, missing thread or interrupt id, bad thread id, over-length and unknown fields."""
    assert client.post("/chat/resume", json=body).status_code == 422


def test_resume_route_maps_an_invalid_resume_to_409(monkeypatch) -> None:
    """AT-11: the route turns InvalidResumeError into a controlled 409 with the reason."""
    def refuse(settings, req):
        raise InvalidResumeError("thread t1 has no pending clarification")

    monkeypatch.setattr(main, "resume_chat", refuse)
    response = client.post("/chat/resume", json={"thread_id": "t1", "interrupt_id": "abc", "message": "hi"})
    assert response.status_code == 409 and response.json()["detail"] == "thread t1 has no pending clarification"


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

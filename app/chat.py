"""Chat service: run the graph on a thread with durable memory and map the final state to a ChatResponse (7.2, 8.2)."""
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.config import Settings
from app.errors import InvalidResumeError, RequestTimeoutError, ThreadBusyError
from app.graph.build import build_graph
from app.graph.tracing import request_context
from app.llm import make_chat_model
from app.retrieval.embeddings import make_embedder
from app.retrieval.search import INDEX_CACHE
from app.schemas.chat import ChatRequest, ChatResponse, Clarification, ResumeRequest

logger = logging.getLogger(__name__)

# Our own state types, registered so the checkpointer may load them (a future LangGraph version blocks unregistered ones)
SAVED_TYPES = [("app.retrieval.filters", "SearchFilters"), ("app.schemas.plan", "QueryPlan"),
               ("app.schemas.search", "RankedChunk"), ("app.schemas.answer", "Citation")]

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_WORKERS: dict[str, threading.Thread] = {}  # the run in progress per thread; a run that timed out keeps going until it ends
_GRAPH = None


def make_checkpointer(path: str) -> SqliteSaver:
    """Open the SQLite checkpoint file; check_same_thread=False is safe because SqliteSaver guards its writes with a lock."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    serde = JsonPlusSerializer(allowed_msgpack_modules=SAVED_TYPES)
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False), serde=serde)


def get_graph(settings: Settings):
    """Build the graph once, with models and the durable checkpointer; raises ModelNotConfiguredError without credentials."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph(settings, lambda: INDEX_CACHE.get(settings), make_embedder(settings), make_chat_model(settings),
                             checkpointer=make_checkpointer(settings.checkpoint_db_path))
    return _GRAPH


@contextmanager
def thread_lock(thread_id: str) -> Iterator[None]:
    """Allow one run per thread at a time: a second request on the same thread fails fast instead of corrupting memory."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(thread_id, threading.Lock())
    if not lock.acquire(blocking=False):
        raise ThreadBusyError(f"a run is already in progress for thread {thread_id}; retry when it finishes")
    worker = _WORKERS.get(thread_id)
    if worker is not None and worker.is_alive():  # an earlier request gave up waiting, but its run cannot be stopped
        lock.release()
        raise ThreadBusyError(f"a run is already in progress for thread {thread_id} (an earlier request timed out and is still finishing); retry when it finishes")
    try:
        yield
    finally:
        lock.release()


def to_response(state: dict, thread_id: str, request_id: str) -> ChatResponse:
    """Turn the graph's result into the public response; a paused graph has '__interrupt__' instead of a final state."""
    if "__interrupt__" in state:
        pending = state["__interrupt__"][0]
        return ChatResponse(thread_id=thread_id, status="needs_clarification", answer=None, citations=[], request_id=request_id,
                            clarification=Clarification(interrupt_id=pending.id, question=pending.value["question"]))
    return ChatResponse(thread_id=thread_id, status=state["status"], answer=state.get("answer"), citations=state.get("citations", []),
                        clarification=None, request_id=request_id)


def pending_interrupts(graph, thread_id: str) -> list:
    """Read the thread's saved state and return the interrupts it is waiting on (empty when it is not paused)."""
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    return [i for task in snapshot.tasks for i in task.interrupts]


def execute(graph, thread_id: str, graph_input, timeout_seconds: float) -> ChatResponse:
    """Run (or resume) the graph on a thread and wait at most timeout_seconds; request_id and thread_id are in every log line.

    A Python thread cannot be killed, so a run that overruns keeps going in the background and its thread stays busy until it
    ends (thread_lock refuses a second run meanwhile). LangGraph's own step_timeout does not help: in a synchronous run it only
    raises after the slow step has already finished (measured). The caller holds the thread lock.
    """
    request_id = uuid.uuid4().hex[:12]
    outcome: dict = {}

    def work() -> None:
        token = request_context.set({"request_id": request_id, "thread_id": thread_id})
        try:
            outcome["state"] = graph.invoke(graph_input, {"configurable": {"thread_id": thread_id}})
        except Exception as exc:  # handed to the waiting request, which maps it to a controlled response
            outcome["error"] = exc
        finally:
            request_context.reset(token)

    worker = threading.Thread(target=work, name=f"run-{thread_id}", daemon=True)
    _WORKERS[thread_id] = worker
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        logger.warning("chat timed out request_id=%s thread_id=%s after %ss; the run continues in the background", request_id, thread_id, timeout_seconds)
        raise RequestTimeoutError(f"the request took longer than {timeout_seconds} seconds; wait a moment, then try again")
    _WORKERS.pop(thread_id, None)
    if "error" in outcome:
        raise outcome["error"]
    state = outcome["state"]
    response = to_response(state, thread_id, request_id)
    logger.info("chat done request_id=%s thread_id=%s status=%s", request_id, thread_id, response.status)
    return response


def run_chat(settings: Settings, request: ChatRequest, graph=None) -> ChatResponse:
    """Run one user message on its thread (generating a thread id if none was sent) and return the structured reply."""
    thread_id = request.thread_id or uuid.uuid4().hex
    graph = graph or get_graph(settings)
    with thread_lock(thread_id):
        if pending_interrupts(graph, thread_id):  # a new message would silently abandon the question we asked
            raise InvalidResumeError(f"thread {thread_id} is waiting for a clarification; answer it with POST /chat/resume")
        return execute(graph, thread_id, {"messages": [HumanMessage(request.message)], "search_mode": request.search_mode,
                                          "top_k": request.top_k, "filters": request.filters}, settings.request_timeout_seconds)


def resume_chat(settings: Settings, request: ResumeRequest, graph=None) -> ChatResponse:
    """Continue a paused thread with the user's clarification; LangGraph would accept a resume on ANY thread, so we check first."""
    graph = graph or get_graph(settings)
    with thread_lock(request.thread_id):
        pending = pending_interrupts(graph, request.thread_id)
        if not pending:
            raise InvalidResumeError(f"thread {request.thread_id} has no pending clarification")
        if pending[0].id != request.interrupt_id:
            raise InvalidResumeError(f"interrupt_id does not match the pending clarification of thread {request.thread_id}")
        return execute(graph, request.thread_id, Command(resume={request.interrupt_id: request.message}), settings.request_timeout_seconds)

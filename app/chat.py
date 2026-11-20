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

from app.config import Settings
from app.errors import ThreadBusyError
from app.graph.build import build_graph
from app.graph.tracing import request_context
from app.llm import make_chat_model
from app.retrieval.embeddings import make_embedder
from app.retrieval.search import INDEX_CACHE
from app.schemas.chat import ChatRequest, ChatResponse, Clarification

logger = logging.getLogger(__name__)

# Our own state types, registered so the checkpointer may load them (a future LangGraph version blocks unregistered ones)
SAVED_TYPES = [("app.retrieval.filters", "SearchFilters"), ("app.schemas.plan", "QueryPlan"),
               ("app.schemas.search", "RankedChunk"), ("app.schemas.answer", "Citation")]

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
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
    try:
        yield
    finally:
        lock.release()


def to_response(state: dict, thread_id: str, request_id: str) -> ChatResponse:
    """Turn the graph's final state into the public response."""
    status = state["status"]
    clarification = Clarification(question=state["clarification_question"]) if status == "needs_clarification" else None
    return ChatResponse(thread_id=thread_id, status=status, answer=state.get("answer"), citations=state.get("citations", []),
                        clarification=clarification, request_id=request_id)


def run_chat(settings: Settings, request: ChatRequest, graph=None) -> ChatResponse:
    """Run one user message on its thread (generating a thread id if none was sent) and return the structured reply."""
    thread_id = request.thread_id or uuid.uuid4().hex
    request_id = uuid.uuid4().hex[:12]
    graph = graph or get_graph(settings)
    with thread_lock(thread_id):
        token = request_context.set({"request_id": request_id, "thread_id": thread_id})
        try:
            state = graph.invoke({"messages": [HumanMessage(request.message)], "search_mode": request.search_mode,
                                  "filters": request.filters}, {"configurable": {"thread_id": thread_id}})
        finally:
            request_context.reset(token)
    logger.info("chat done request_id=%s thread_id=%s status=%s", request_id, thread_id, state["status"])
    return to_response(state, thread_id, request_id)

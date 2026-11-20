"""POST /chat request and response (8.2)."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.retrieval.filters import SearchFilters
from app.schemas.answer import Citation

MAX_MESSAGE_CHARS = 2000  # documented maximum message length
ThreadId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]  # safe to use as a key and in logs


class ChatRequest(BaseModel):
    """One user message on a conversation thread; omit thread_id to start a new conversation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    thread_id: ThreadId | None = None
    search_mode: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    filters: SearchFilters = Field(default_factory=SearchFilters)


class Clarification(BaseModel):
    """What the user must answer for the pending clarification (the interrupt id is added in block 7)."""

    question: str


class ChatResponse(BaseModel):
    """Every chat reply: the thread id to reuse, the outcome, the answer and its verified citations."""

    thread_id: str
    status: Literal["answered", "needs_clarification", "insufficient_evidence", "out_of_scope"]
    answer: str | None
    citations: list[Citation]
    clarification: Clarification | None
    request_id: str

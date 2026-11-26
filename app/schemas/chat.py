"""POST /chat request and response (8.2)."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.retrieval.filters import SearchFilters
from app.schemas.answer import Citation
from app.schemas.examples import CHAT_REQUEST, CHAT_RESPONSES, RESUME_REQUEST

MAX_MESSAGE_CHARS = 2000  # documented maximum message length
ThreadId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]  # safe to use as a key and in logs


class ChatRequest(BaseModel):
    """One user message on a conversation thread; omit thread_id to start a new conversation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", json_schema_extra={"examples": [CHAT_REQUEST]})

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    thread_id: ThreadId | None = None
    search_mode: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)  # how many chunks the answer may use (same bounds as /search)
    filters: SearchFilters = Field(default_factory=SearchFilters)


class ResumeRequest(BaseModel):
    """The user's answer to a pending clarification, tied to the interrupt it answers."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", json_schema_extra={"examples": [RESUME_REQUEST]})

    thread_id: ThreadId
    interrupt_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class Clarification(BaseModel):
    """The pending interrupt: which one it is and the question to answer."""

    interrupt_id: str
    question: str


class ChatResponse(BaseModel):
    """Every chat reply: the thread id to reuse, the outcome, the answer and its verified citations."""

    model_config = ConfigDict(json_schema_extra={"examples": CHAT_RESPONSES})

    thread_id: str
    status: Literal["answered", "needs_clarification", "insufficient_evidence", "out_of_scope"]
    answer: str | None
    citations: list[Citation]
    clarification: Clarification | None
    request_id: str

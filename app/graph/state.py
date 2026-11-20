"""Typed state of the question-answering graph (7.2): which fields persist and which reset each question."""
from typing import Annotated, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.retrieval.filters import SearchFilters
from app.schemas.answer import Citation
from app.schemas.plan import QueryPlan
from app.schemas.search import RankedChunk


class GraphState(TypedDict, total=False):
    """Every field the nodes read or write. Parallel nodes write DIFFERENT keys, so no reducer is needed for them."""

    # --- persists for the whole thread (conversation memory); add_messages APPENDS new messages
    messages: Annotated[list[AnyMessage], add_messages]

    # --- supplied with every request, overwritten each turn
    search_mode: Literal["lexical", "semantic", "hybrid"]
    filters: SearchFilters  # filters the caller sent
    top_k: int

    # --- belongs to ONE question: start_turn resets all of these
    plan: QueryPlan | None
    standalone_query: str
    effective_filters: SearchFilters  # caller's filters, completed by filters the user stated in words
    lexical_candidates: list[RankedChunk]  # written only by the lexical node
    semantic_candidates: list[RankedChunk]  # written only by the semantic node
    fused: list[RankedChunk]
    evidence: list[RankedChunk]  # the final chunks the answer may use
    ranking_stage: str
    rerank_note: str | None
    clarification_attempts: int
    clarification_question: str | None
    status: str
    answer: str | None
    citations: list[Citation]  # verified sources of the answer; empty unless status is 'answered'

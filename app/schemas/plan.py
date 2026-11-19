
"""The query plan: the validated, structured result of interpreting a question (7.1)."""
from typing import Literal

from pydantic import BaseModel, model_validator


class PlanFilters(BaseModel):
    """Filters the user explicitly asked for in words (for example 'laws from 2023'); otherwise all None."""

    year: int | None = None
    doc_type: Literal["Law", "Regulation", "Resolution"] | None = None


class QueryPlan(BaseModel):
    """Intent, a self-contained version of the question, filters, and whether we must ask the user something first."""

    intent: Literal["legal_question", "out_of_scope"]
    standalone_query: str  # the question rewritten so it makes sense without the chat history
    filters: PlanFilters
    needs_clarification: bool
    clarification_question: str | None

    @model_validator(mode="after")
    def check_consistency(self) -> "QueryPlan":
        """An out-of-scope question is never clarified, and a clarification must come with a question to ask."""
        if self.intent == "out_of_scope" and self.needs_clarification:
            raise ValueError("an out-of-scope question cannot need clarification")
        if self.needs_clarification and not (self.clarification_question or "").strip():
            raise ValueError("needs_clarification requires a clarification_question")
        return self

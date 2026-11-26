"""The examples shown in /docs must be valid: an example the API itself would reject is worse than none."""
import pytest
from pydantic import BaseModel

from app.schemas.chat import ChatRequest, ChatResponse, ResumeRequest
from app.schemas.examples import CHAT_REQUEST, CHAT_RESPONSES, RESUME_REQUEST, SEARCH_REQUEST, SEARCH_RESPONSE
from app.schemas.search import SearchRequest, SearchResponse


@pytest.mark.parametrize(
    ("model", "example"),
    [(ChatRequest, CHAT_REQUEST), (ResumeRequest, RESUME_REQUEST), (SearchRequest, SEARCH_REQUEST), (SearchResponse, SEARCH_RESPONSE)]
    + [(ChatResponse, example) for example in CHAT_RESPONSES],
)
def test_every_documented_example_is_accepted_by_its_own_model(model: type[BaseModel], example: dict) -> None:
    model.model_validate(example)


def test_the_chat_examples_cover_all_four_outcomes() -> None:
    assert {example["status"] for example in CHAT_RESPONSES} == {"answered", "needs_clarification", "insufficient_evidence", "out_of_scope"}


def test_the_generated_openapi_document_carries_the_examples() -> None:
    from app.api.main import app

    schemas = app.openapi()["components"]["schemas"]
    for name in ("ChatRequest", "ResumeRequest", "ChatResponse", "SearchRequest", "SearchResponse"):
        assert schemas[name].get("examples"), f"{name} has no example in /docs"

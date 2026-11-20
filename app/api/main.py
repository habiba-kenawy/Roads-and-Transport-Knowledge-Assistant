"""FastAPI application: routes only, no business logic."""
from typing import Callable, TypeVar

from fastapi import FastAPI, HTTPException

from app.config import Settings
from app.chat import resume_chat, run_chat
from app.errors import IndexNotReadyError, InvalidResumeError, ModelCallError, ModelNotConfiguredError, ThreadBusyError
from app.indexing import build_index
from app.ingestion.store import index_available
from app.retrieval.search import perform_search
from app.schemas.chat import ChatRequest, ChatResponse, ResumeRequest
from app.schemas.health import HealthResponse
from app.schemas.ingest import IngestReport
from app.schemas.search import SearchRequest, SearchResponse

app = FastAPI(title="Roads and Transport Knowledge Assistant")
settings = Settings()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report readiness so we can tell what is missing before using other endpoints."""
    return HealthResponse(
        status="ok",
        model_configured=settings.model_configured,
        index_available=index_available(settings.db_path),
    )


@app.post("/ingest", response_model=IngestReport)
def ingest() -> IngestReport:
    """Ingest the approved local corpus and embed its chunks; synchronous because the dataset is small."""
    return build_index(settings)


T = TypeVar("T")


def controlled(call: Callable[[], T]) -> T:
    """Run a service call and turn known failures into clear, controlled HTTP responses (never a stack trace)."""
    try:
        return call()
    except (ThreadBusyError, InvalidResumeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))  # thread still running, or the resume does not match its saved state
    except (IndexNotReadyError, ModelNotConfiguredError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))  # service not ready: tell the caller what to do
    except ModelCallError as exc:
        raise HTTPException(status_code=502, detail=str(exc))  # an upstream model call failed


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Return ranked chunks for a query in the chosen mode, so retrieval can be inspected without answer generation."""
    return controlled(lambda: perform_search(settings, request))


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Answer a message on a conversation thread (memory is kept per thread_id), or abstain, refuse, or ask for clarification."""
    return controlled(lambda: run_chat(settings, request))


@app.post("/chat/resume", response_model=ChatResponse)
def chat_resume(request: ResumeRequest) -> ChatResponse:
    """Answer the pending clarification of a paused thread and continue the same workflow (409 if nothing is pending)."""
    return controlled(lambda: resume_chat(settings, request))

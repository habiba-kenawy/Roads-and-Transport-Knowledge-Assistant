"""FastAPI application: routes only, no business logic."""
from fastapi import FastAPI, HTTPException

from app.config import Settings
from app.errors import IndexNotReadyError, ModelCallError, ModelNotConfiguredError
from app.indexing import build_index
from app.ingestion.store import index_available
from app.retrieval.search import perform_search
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


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Return ranked chunks for a query in the chosen mode, so retrieval can be inspected without answer generation."""
    try:
        return perform_search(settings, request)
    except (IndexNotReadyError, ModelNotConfiguredError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))  # service not ready: tell the caller what to do
    except ModelCallError as exc:
        raise HTTPException(status_code=502, detail=str(exc))  # an upstream model call failed

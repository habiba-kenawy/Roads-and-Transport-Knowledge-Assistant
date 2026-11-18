"""FastAPI application: routes only, no business logic."""
from fastapi import FastAPI

from app.config import Settings
from app.ingestion.pipeline import ingest_all
from app.ingestion.store import index_available
from app.schemas.health import HealthResponse
from app.schemas.ingest import IngestReport

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
    """Ingest the approved local corpus; synchronous because the dataset is small."""
    return ingest_all(settings)

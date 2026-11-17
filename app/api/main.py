"""FastAPI application: routes only, no business logic."""
from fastapi import FastAPI

from app.config import Settings
from app.schemas.health import HealthResponse

app = FastAPI(title="Roads and Transport Knowledge Assistant")
settings = Settings()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report readiness so we can tell what is missing before using other endpoints."""
    return HealthResponse(
        status="ok",
        model_configured=settings.model_configured,
        index_available=False,  # placeholder: Phase 2 replaces this with a real index check
    )

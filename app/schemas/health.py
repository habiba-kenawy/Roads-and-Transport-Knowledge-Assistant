"""Response model for GET /health."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Shape of the health reply; contains flags only, never credentials."""

    status: str
    model_configured: bool
    index_available: bool




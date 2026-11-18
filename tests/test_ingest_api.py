"""Tests for the POST /ingest route; the pipeline itself is replaced by a FAKE so no real documents are read."""
from fastapi.testclient import TestClient

from app.api import main
from app.schemas.ingest import IngestError, IngestReport

client = TestClient(main.app, raise_server_exceptions=False)  # return a 500 response instead of re-raising


def test_ingest_route_returns_the_report_from_the_pipeline(monkeypatch) -> None:
    """The route must call build_index and return its report unchanged (the API layer stays thin)."""
    report = IngestReport(indexed=2, skipped=1, failed=1, errors=[IngestError(doc_id="fake", reason="FAKE problem")],
                          embedded=5, embedding_error=None)
    monkeypatch.setattr(main, "build_index", lambda settings: report)
    response = client.post("/ingest")
    assert response.status_code == 200
    assert response.json() == report.model_dump()

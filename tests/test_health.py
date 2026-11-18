"""Tests for GET /health (credentials below are FAKE; the real .env is never used)."""
from fastapi.testclient import TestClient

from app.api import main
from app.config import Settings

client = TestClient(main.app)


def test_health_returns_declared_shape_and_hides_secrets(monkeypatch, tmp_path) -> None:
    """Protects the contract: three flags only, and no credential ever appears in the reply."""
    fake = Settings(_env_file=None, azure_openai_endpoint="https://fake.example/v1", azure_openai_api_key="FAKE-KEY-123", db_path=str(tmp_path / "none.sqlite"))
    monkeypatch.setattr(main, "settings", fake)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_configured": True, "index_available": False}
    assert "FAKE-KEY-123" not in response.text
    assert "fake.example" not in response.text


def test_health_reports_model_not_configured_instead_of_failing(monkeypatch, tmp_path) -> None:
    """Protects the choice that /health still answers when credentials are missing."""
    monkeypatch.setattr(main, "settings", Settings(_env_file=None, azure_openai_endpoint=None, azure_openai_api_key=None, db_path=str(tmp_path / "none.sqlite")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_configured"] is False

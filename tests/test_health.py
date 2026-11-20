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


def test_cors_allows_the_configured_origin_and_refuses_others() -> None:
    """The browser page may call the API only from the configured origin: header present for it, absent for any other."""
    allowed = client.get("/health", headers={"Origin": "http://localhost:5180"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5180"
    other = client.get("/health", headers={"Origin": "http://evil.example"})
    assert other.status_code == 200 and "access-control-allow-origin" not in other.headers  # the server answers; the browser blocks the page


def test_cors_preflight_is_limited_to_the_origin_methods_and_headers_we_use() -> None:
    """A browser first asks permission (OPTIONS); only our origin, POST/GET and Content-Type are accepted."""
    ask = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = client.options("/chat/resume", headers={"Origin": "http://localhost:5180", **ask})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:5180"
    assert "DELETE" not in ok.headers["access-control-allow-methods"]
    refused = client.options("/chat/resume", headers={"Origin": "http://evil.example", **ask})
    assert refused.status_code == 400 and "access-control-allow-origin" not in refused.headers
    odd_header = client.options("/chat", headers={"Origin": "http://localhost:5180", "Access-Control-Request-Method": "POST",
                                                  "Access-Control-Request-Headers": "x-secret-thing"})
    assert odd_header.status_code == 400


def test_cors_origin_list_drops_blanks_and_the_wildcard() -> None:
    """No wildcard can sneak in through the environment variable."""
    settings = Settings(_env_file=None, cors_origins=" http://localhost:5180 , ,*, https://example.org ")
    assert settings.cors_origin_list == ["http://localhost:5180", "https://example.org"]

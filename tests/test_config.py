"""Tests for Settings: secrets stay hidden and missing credentials don't crash (all values below are FAKE)."""
from app.config import Settings


def test_secret_key_is_not_visible_in_repr_or_str() -> None:
    """Protects against leaking the API key into logs or error messages."""
    s = Settings(_env_file=None, azure_openai_endpoint="https://fake.example/v1", azure_openai_api_key="FAKE-KEY-123")
    assert "FAKE-KEY-123" not in repr(s)
    assert "FAKE-KEY-123" not in str(s)
    assert s.azure_openai_api_key.get_secret_value() == "FAKE-KEY-123"


def test_missing_credentials_do_not_crash_and_report_not_configured() -> None:
    """Protects the choice that /health can still run when the model is not configured."""
    s = Settings(_env_file=None, azure_openai_endpoint=None, azure_openai_api_key=None)
    assert s.model_configured is False


def test_embedding_url_falls_back_to_main_endpoint() -> None:
    """Protects the optional separate embeddings endpoint rule."""
    s = Settings(_env_file=None, azure_openai_endpoint="https://fake.example/v1", embedding_endpoint=None)
    assert s.embedding_base_url == "https://fake.example/v1"

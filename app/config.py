"""Application settings, read once from .env / environment variables."""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings; missing model credentials are allowed so /health can still report the problem."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None  # SecretStr prints as ********
    embedding_endpoint: str | None = None  # optional: falls back to azure_openai_endpoint
    chat_deployment: str = "gpt-4.1-mini"
    embedding_deployment: str = "text-embedding-3-small"
    chunk_size: int = 1000  # max characters per chunk (DATA-03); articles longer than this are split
    chunk_overlap: int = 150  # characters repeated between neighbouring pieces of a long article
    retrieval_candidates: int = 20  # candidates each retriever returns, and the most the reranker ever sees (bounded)
    checkpoint_db_path: str = "data/checkpoints.sqlite"  # conversation memory (LangGraph checkpoints), git-ignored
    db_path: str = "data/index.sqlite"  # file-backed SQLite store for chunks (git-ignored)

    @property
    def embedding_base_url(self) -> str | None:
        """Return the embeddings endpoint, or the main endpoint when no separate one is set."""
        return self.embedding_endpoint or self.azure_openai_endpoint

    @property
    def model_configured(self) -> bool:
        """Say whether credentials exist, without exposing them (used by /health)."""
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

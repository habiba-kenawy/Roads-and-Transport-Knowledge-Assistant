"""Application settings, read once from .env / environment variables."""
from pydantic import Field, SecretStr
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
    retrieval_candidates: int = 10  # candidates each retriever returns, and what the reranker sees (never below top_k; measured: 10 is as good as 20 and ~1 s faster)
    model_timeout_seconds: int = Field(default=30, gt=0)  # one model call (chat or embeddings); the client gives up after this long
    model_max_retries: int = Field(default=2, ge=0)  # extra tries after a failed model call
    request_timeout_seconds: int = Field(default=60, gt=0)  # the whole /chat or /chat/resume call: after this the caller gets a 504
    checkpoint_db_path: str = "data/checkpoints.sqlite"  # conversation memory (LangGraph checkpoints), git-ignored
    db_path: str = "data/index.sqlite"  # file-backed SQLite store for chunks (git-ignored)
    cors_origins: str = "http://localhost:5180"  # comma-separated web page origins allowed to call the API (our Vite dev server)

    @property
    def embedding_base_url(self) -> str | None:
        """Return the embeddings endpoint, or the main endpoint when no separate one is set."""
        return self.embedding_endpoint or self.azure_openai_endpoint

    @property
    def cors_origin_list(self) -> list[str]:
        """Split the comma-separated CORS_ORIGINS value into a clean list (no blanks, no wildcard entries)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip() and o.strip() != "*"]

    @property
    def model_configured(self) -> bool:
        """Say whether credentials exist, without exposing them (used by /health)."""
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

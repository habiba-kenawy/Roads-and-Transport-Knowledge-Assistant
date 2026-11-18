"""Create and store chunk embeddings with the Azure embedding model (RAG-01, semantic search)."""
import sqlite3

import numpy as np
from langchain_openai import OpenAIEmbeddings

from app.config import Settings

BATCH = 64  # texts per API request: small enough for any deployment limit


class ModelNotConfiguredError(Exception):
    """A model call is needed but endpoint/key are missing; the API will turn this into a controlled error."""


def make_embedder(settings: Settings) -> OpenAIEmbeddings:
    """Build the embeddings client from settings; the key is read only here and never logged."""
    if not settings.model_configured or not settings.embedding_base_url:
        raise ModelNotConfiguredError("embedding model is not configured (check .env)")
    return OpenAIEmbeddings(
        model=settings.embedding_deployment,  # on Azure this is the deployment name
        base_url=settings.embedding_base_url,
        api_key=settings.azure_openai_api_key.get_secret_value(),
        check_embedding_ctx_length=False,  # our chunks are far below the token limit; avoids tiktoken downloads
        max_retries=2,
        timeout=30,
        chunk_size=BATCH,
    )


def embed_missing(conn: sqlite3.Connection, embedder, model: str) -> int:
    """Embed chunks that have no vector yet and drop vectors of removed chunks; safe to run repeatedly."""
    with conn:
        conn.execute("DELETE FROM embeddings WHERE model != ? OR chunk_id NOT IN (SELECT chunk_id FROM chunks)", (model,))
    rows = conn.execute("SELECT chunk_id, text FROM chunks WHERE chunk_id NOT IN (SELECT chunk_id FROM embeddings)").fetchall()
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        vectors = embedder.embed_documents([text for _, text in batch])
        with conn:  # commit per batch so a late failure keeps earlier work
            conn.executemany(
                "INSERT INTO embeddings (chunk_id, model, vector) VALUES (?, ?, ?)",
                [(cid, model, np.asarray(v, dtype=np.float32).tobytes()) for (cid, _), v in zip(batch, vectors)],
            )
    return len(rows)

"""Embeddings (façade -> app.services.embedding_service*)."""
from app.services.embedding_service import (  # noqa: F401
    EmbeddingError,
    EmbeddingService,
    to_pgvector,
)
from app.services.embedding_service_ollama import EmbeddingServiceOllama  # noqa: F401

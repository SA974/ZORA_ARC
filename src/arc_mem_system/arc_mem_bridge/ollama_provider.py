"""Provider Ollama : embeddings + healthcheck (façade -> app.services.*)."""
from app.services.embedding_service_ollama import (  # noqa: F401
    EmbeddingError,
    EmbeddingServiceOllama,
    OllamaSettings,
)
from app.services.provider_health import check_ollama, preflight_embedder  # noqa: F401

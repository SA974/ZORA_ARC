"""Bloc ``arc_mem_bridge`` — pont Hermes ↔ PostgreSQL et orchestration de l'ingestion PDF.

Façade stable au-dessus de ``app.*``. Sous-modules nommés (chunking, embeddings,
ollama_provider, postgres_client, pdf_ingestion, pipeline, healthcheck) disponibles pour
un import ciblé conforme à l'arborescence cible.
"""
from __future__ import annotations

# Configuration
from app.config import Settings, get_settings, mask_secret  # noqa: F401

# PostgreSQL
from app.db import (  # noqa: F401
    DatabaseHealth,
    check_database_health,
    get_connection,
    test_connection,
)

# PDF + chunking
from app.services.pdf_service import (  # noqa: F401
    PageChunk,
    chunk_pages,
    compute_file_hash,
    extract_pdf_pages,
    sanitize_text,
)

# Embeddings (recherche OpenAI-compat + ingestion Ollama natif)
from app.services.embedding_service import (  # noqa: F401
    EmbeddingError,
    EmbeddingService,
    to_pgvector,
)
from app.services.embedding_service_ollama import (  # noqa: F401
    EmbeddingServiceOllama,
    OllamaSettings,
)

# Provider / healthcheck
from app.services.provider_health import check_ollama, preflight_embedder  # noqa: F401

# Ingestion PDF + pipeline
from app.services.document_ingestion import (  # noqa: F401
    get_embedder,
    ingest_folder,
    ingest_pdf_file,
)
from app.services.ingestion_pipeline import IngestionPipeline  # noqa: F401

__all__ = [
    "Settings", "get_settings", "mask_secret",
    "DatabaseHealth", "check_database_health", "get_connection", "test_connection",
    "PageChunk", "chunk_pages", "compute_file_hash", "extract_pdf_pages", "sanitize_text",
    "EmbeddingError", "EmbeddingService", "to_pgvector",
    "EmbeddingServiceOllama", "OllamaSettings",
    "check_ollama", "preflight_embedder",
    "get_embedder", "ingest_folder", "ingest_pdf_file", "IngestionPipeline",
]

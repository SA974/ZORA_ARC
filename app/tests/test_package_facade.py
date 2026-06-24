"""Vérifie que les deux blocs src/arc_mem_system exposent bien l'implémentation app.* (shim)."""
from __future__ import annotations


def test_arc_mem_bridge_facade_reexports_app():
    from arc_mem_system import arc_mem_bridge as bridge
    from app.services.document_ingestion import ingest_pdf_file
    from app.services.embedding_service_ollama import EmbeddingServiceOllama

    # mêmes objets : la façade ne duplique pas, elle ré-exporte.
    assert bridge.ingest_pdf_file is ingest_pdf_file
    assert bridge.EmbeddingServiceOllama is EmbeddingServiceOllama
    for name in ("ingest_folder", "IngestionPipeline", "get_connection", "preflight_embedder",
                 "chunk_pages", "EmbeddingService", "get_settings"):
        assert hasattr(bridge, name), name


def test_memory_rag_core_facade_reexports_app():
    from arc_mem_system import memory_rag_core as core
    from app.services.hmem_retrieval import score_candidate
    from app.services.memgraph_service import MemGraphService

    assert core.score_candidate is score_candidate
    assert core.MemGraphService is MemGraphService
    for name in ("HMemRouter", "HMemBuilder", "hmem_retrieve", "TemporalService", "ExtractionService"):
        assert hasattr(core, name), name


def test_named_submodules_importable():
    from arc_mem_system.arc_mem_bridge import chunking, embeddings, ollama_provider, healthcheck
    from arc_mem_system.memory_rag_core import scoring
    from arc_mem_system.memory_rag_core.hmem import HMemRouter
    from arc_mem_system.memory_rag_core.memgraphrag import MemGraphService

    assert chunking.chunk_pages and embeddings.EmbeddingService
    assert ollama_provider.check_ollama and healthcheck.check_database_health
    assert scoring.score_candidate and HMemRouter and MemGraphService

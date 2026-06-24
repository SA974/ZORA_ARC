"""Tests de l'embedder Ollama : régression bug retry + validation de dimension.

Aucune dépendance externe (ni Ollama ni PostgreSQL) : httpx est simulé via MockTransport.
"""
from __future__ import annotations

import httpx
import pytest

from app.services.embedding_service import EmbeddingError as SharedEmbeddingError
from app.services.embedding_service_ollama import (
    EmbeddingError,
    EmbeddingServiceOllama,
    OllamaSettings,
)


def _service_with_response(monkeypatch, handler) -> EmbeddingServiceOllama:
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    settings = OllamaSettings(base_url="http://x", embedding_model="nomic-embed-text", embedding_dim=768)
    return EmbeddingServiceOllama(settings)


def test_embedding_error_is_shared_class():
    """Régression : l'embedder Ollama DOIT lever la MÊME EmbeddingError que
    l'EmbeddingService OpenAI-compat, sinon `_embed_with_retry` ne l'attrape pas."""
    assert EmbeddingError is SharedEmbeddingError


def test_returns_vectors_on_valid_response(monkeypatch):
    svc = _service_with_response(
        monkeypatch, lambda req: httpx.Response(200, json={"embedding": [0.1] * 768})
    )
    out = svc.embed_texts(["bonjour", "monde"])
    assert len(out) == 2
    assert all(len(v) == 768 for v in out)


def test_wrong_dimension_raises(monkeypatch):
    """Un modèle renvoyant 1024D au lieu de 768D doit lever, pas corrompre pgvector."""
    svc = _service_with_response(
        monkeypatch, lambda req: httpx.Response(200, json={"embedding": [0.1] * 1024})
    )
    with pytest.raises(EmbeddingError, match="dimension inattendue 1024"):
        svc.embed_texts(["x"])


def test_empty_embedding_raises(monkeypatch):
    svc = _service_with_response(monkeypatch, lambda req: httpx.Response(200, json={"embedding": []}))
    with pytest.raises(EmbeddingError, match="vide"):
        svc.embed_texts(["x"])


def test_http_error_raises_embedding_error(monkeypatch):
    svc = _service_with_response(monkeypatch, lambda req: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(EmbeddingError):
        svc.embed_texts(["x"])


def test_empty_input_returns_empty():
    svc = EmbeddingServiceOllama(OllamaSettings(base_url="http://x", embedding_model="m"))
    assert svc.embed_texts([]) == []


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_EMBEDDING_DIM", "768")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "42")
    s = OllamaSettings()
    assert s.embedding_dim == 768
    assert s.embedding_timeout == 42

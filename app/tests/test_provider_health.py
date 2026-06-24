"""Tests des healthchecks provider (preflight embedder + check_ollama), sans Ollama réel."""
from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest

from app.services.embedding_service import EmbeddingError
from app.services.embedding_service_ollama import OllamaSettings
from app.services.provider_health import check_ollama, preflight_embedder


@dataclass
class _Settings:
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768


class _FakeEmbedder:
    def __init__(self, *, return_dim=768, configured=True, raises=False):
        # settings.embedding_dim reste 768 (attendu) ; return_dim = ce que renvoie réellement l'API.
        self.settings = _Settings(embedding_dim=768)
        self._return_dim = return_dim
        self._configured = configured
        self._raises = raises

    def configured(self):
        return self._configured

    def embed_texts(self, texts, *, input_type="passage"):
        if self._raises:
            raise EmbeddingError("Ollama injoignable")
        return [[0.0] * self._return_dim for _ in texts]


def test_preflight_ok():
    assert preflight_embedder(_FakeEmbedder())["ok"] is True


def test_preflight_not_configured():
    r = preflight_embedder(_FakeEmbedder(configured=False))
    assert r["ok"] is False and "configuré" in r["error"]


def test_preflight_dimension_mismatch():
    r = preflight_embedder(_FakeEmbedder(return_dim=1024))
    assert r["ok"] is False and "1024" in r["error"]


def test_preflight_provider_down():
    r = preflight_embedder(_FakeEmbedder(raises=True))
    assert r["ok"] is False and "injoignable" in r["error"]


def _patch_tags(monkeypatch, payload, status=200):
    transport = httpx.MockTransport(lambda req: httpx.Response(status, json=payload))
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real(*a, transport=transport, **k))


def test_check_ollama_model_present(monkeypatch):
    _patch_tags(monkeypatch, {"models": [{"name": "nomic-embed-text:latest"}, {"name": "qwen:14b"}]})
    r = check_ollama(OllamaSettings(base_url="http://x", embedding_model="nomic-embed-text"))
    assert r["ok"] and r["reachable"] and r["model_present"]


def test_check_ollama_model_absent(monkeypatch):
    _patch_tags(monkeypatch, {"models": [{"name": "qwen:14b"}]})
    r = check_ollama(OllamaSettings(base_url="http://x", embedding_model="nomic-embed-text"))
    assert r["reachable"] and not r["model_present"] and not r["ok"]
    assert "ollama pull" in r["error"]


def test_check_ollama_unreachable(monkeypatch):
    def boom(req):
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(boom)
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real(*a, transport=transport, **k))
    r = check_ollama(OllamaSettings(base_url="http://x", embedding_model="nomic-embed-text"))
    assert r["ok"] is False and r["reachable"] is False and "injoignable" in r["error"]

"""Healthchecks du provider d'embeddings/LLM (Ollama), pour échouer VITE et clairement.

Deux usages :
- `preflight_embedder(embedder)` : avant un batch d'ingestion, vérifie en un appel réel
  que l'embedder répond ET renvoie la bonne dimension. Évite de scanner 1000 PDF pour
  échouer au premier embedding.
- `check_ollama(settings)` : diagnostic riche exposé par /health (joignable, modèles présents).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.embedding_service_ollama import OllamaSettings

logger = logging.getLogger(__name__)


def preflight_embedder(embedder: Any) -> dict[str, Any]:
    """Test minimal et réel de l'embedder. Retourne {ok, dim, model, error}."""
    model = getattr(embedder.settings, "embedding_model", None)
    expected = getattr(embedder.settings, "embedding_dim", None)
    if not embedder.configured():
        return {"ok": False, "model": model, "error": "embedder non configuré (model/base_url/api_key)"}
    try:
        vec = embedder.embed_texts(["healthcheck"], input_type="passage")[0]
    except Exception as exc:  # noqa: BLE001 - on veut un diagnostic, pas un crash
        return {"ok": False, "model": model, "error": f"{type(exc).__name__}: {exc}"}
    if expected and len(vec) != expected:
        return {"ok": False, "model": model, "dim": len(vec),
                "error": f"dimension {len(vec)} != attendu {expected}"}
    return {"ok": True, "model": model, "dim": len(vec)}


def check_ollama(settings: OllamaSettings | None = None) -> dict[str, Any]:
    """Diagnostic Ollama pour /health : joignable, liste des modèles, modèle d'embedding présent."""
    s = settings or OllamaSettings()
    base = s.base_url.rstrip("/")
    out: dict[str, Any] = {"ok": False, "base_url": base, "reachable": False,
                           "embedding_model": s.embedding_model, "model_present": False}
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{base}/api/tags")
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
        out["reachable"] = True
        out["models"] = models
        # tolère le suffixe ':latest' (nomic-embed-text == nomic-embed-text:latest)
        out["model_present"] = any(
            m == s.embedding_model or m.split(":")[0] == s.embedding_model.split(":")[0]
            for m in models
        )
        out["ok"] = out["model_present"]
        if not out["model_present"]:
            out["error"] = f"modèle '{s.embedding_model}' absent (ollama pull {s.embedding_model})"
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"Ollama injoignable: {type(exc).__name__}"
    return out

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

# On réutilise LA MÊME classe d'erreur que l'EmbeddingService OpenAI-compatible.
# Indispensable : `document_ingestion._embed_with_retry` attrape `EmbeddingError`
# importé depuis ce module-là ; si l'embedder Ollama levait sa propre classe, le
# retry ne l'attraperait jamais et l'échec remonterait sans relance.
from app.services.embedding_service import EmbeddingError

logger = logging.getLogger(__name__)


@dataclass
class OllamaSettings:
    base_url: str = ""
    embedding_model: str = ""
    embedding_dim: int = 768
    embedding_batch_size: int = 64
    embedding_timeout: int = 120

    def __post_init__(self):
        """Lire les paramètres depuis les vars d'env (profil Hermes) avec defaults sûrs."""
        if not self.base_url:
            self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if not self.embedding_model:
            self.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.embedding_dim = int(os.getenv("OLLAMA_EMBEDDING_DIM", str(self.embedding_dim)))
        self.embedding_timeout = int(os.getenv("OLLAMA_TIMEOUT", str(self.embedding_timeout)))


class EmbeddingServiceOllama:
    """Wrapper HTTP pour Ollama (remplace NVIDIA NIM).

    Robustesse :
    - timeout configurable (OLLAMA_TIMEOUT) ;
    - validation stricte de la dimension (refuse un modèle qui renverrait une
      dimension != embedding_dim, ce qui corromprait silencieusement pgvector) ;
    - erreurs explicites via `EmbeddingError` (classe partagée -> retry effectif).
    """

    def __init__(self, settings: OllamaSettings | None = None):
        self.settings = settings or OllamaSettings()

    def configured(self) -> bool:
        return bool(self.settings.embedding_model and self.settings.base_url)

    def embed_texts(self, texts: list[str], *, input_type: str = "passage") -> list[list[float]]:
        """Vectorise une liste de textes via Ollama /api/embeddings.

        `input_type` est accepté pour compat d'interface avec EmbeddingService mais
        Ollama/nomic ne distingue pas passage/query : il est ignoré côté API.
        """
        if not texts:
            return []
        if not self.configured():
            raise EmbeddingError("embedder Ollama non configuré (model/base_url manquant)")

        dim = self.settings.embedding_dim
        embeddings: list[list[float]] = []
        with httpx.Client(timeout=self.settings.embedding_timeout) as client:
            for text in texts:
                try:
                    resp = client.post(
                        f"{self.settings.base_url.rstrip('/')}/api/embeddings",
                        json={"model": self.settings.embedding_model, "prompt": text},
                    )
                    resp.raise_for_status()
                    embedding = resp.json().get("embedding", [])
                except httpx.HTTPStatusError as exc:
                    raise EmbeddingError(
                        f"HTTP {exc.response.status_code} d'Ollama (modèle "
                        f"'{self.settings.embedding_model}' absent ? -> ollama pull)"
                    ) from exc
                except httpx.RequestError as exc:
                    raise EmbeddingError(f"Ollama injoignable ({type(exc).__name__})") from exc

                if not embedding:
                    raise EmbeddingError("Ollama a renvoyé un embedding vide")
                if len(embedding) != dim:
                    raise EmbeddingError(
                        f"dimension inattendue {len(embedding)} (attendu {dim}) "
                        f"-> modèle '{self.settings.embedding_model}' incohérent avec la colonne vector({dim})"
                    )
                embeddings.append(embedding)

        if len(embeddings) != len(texts):
            raise EmbeddingError(
                f"Embedding count mismatch: attendu {len(texts)}, obtenu {len(embeddings)}"
            )
        return embeddings

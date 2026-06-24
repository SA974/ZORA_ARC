from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# nv-embedqa-e5-v5 (et les NIM e5) distinguent les vecteurs "passage" (stockage)
# des vecteurs "query" (recherche). Mélanger les deux dégrade la similarité cosinus.
VALID_INPUT_TYPES = ("passage", "query")


def to_pgvector(vec: list[float]) -> str:
    """Sérialise un vecteur Python au format littéral pgvector '[v1,v2,...]' (cast ::vector)."""
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


class EmbeddingError(RuntimeError):
    """Erreur d'appel au fournisseur d'embeddings (réseau, auth, format)."""


class EmbeddingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def configured(self) -> bool:
        s = self.settings
        return bool(s.embedding_model and s.embedding_base_url and s.embedding_api_key.get_secret_value())

    def _endpoint(self) -> str:
        return f"{self.settings.embedding_base_url.rstrip('/')}/embeddings"

    def embed_texts(self, texts: list[str], input_type: str = "passage") -> list[list[float]]:
        """Vectorise une liste de textes. Lève EmbeddingError en cas d'échec.

        input_type: 'passage' pour le stockage, 'query' pour la recherche.
        """
        if input_type not in VALID_INPUT_TYPES:
            raise ValueError(f"input_type invalide: {input_type!r} (attendu {VALID_INPUT_TYPES})")
        if not self.configured():
            raise EmbeddingError("embedding provider non configuré (model/base_url/api_key manquant)")
        if not texts:
            return []

        out: list[list[float]] = []
        batch = max(1, self.settings.embedding_batch_size)
        headers = {
            "Authorization": f"Bearer {self.settings.embedding_api_key.get_secret_value()}",
            "Accept": "application/json",
        }
        with httpx.Client(timeout=self.settings.embedding_timeout) as client:
            for start in range(0, len(texts), batch):
                window = texts[start : start + batch]
                payload = {
                    "input": window,
                    "model": self.settings.embedding_model,
                    "input_type": input_type,
                    "encoding_format": "float",
                    "truncate": "END",
                }
                try:
                    resp = client.post(self._endpoint(), headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()["data"]
                except httpx.HTTPStatusError as exc:
                    raise EmbeddingError(f"HTTP {exc.response.status_code} du fournisseur d'embeddings") from exc
                except Exception as exc:  # noqa: BLE001
                    raise EmbeddingError(f"appel embeddings échoué: {type(exc).__name__}") from exc
                ordered = sorted(data, key=lambda item: item.get("index", 0))
                vectors = [item["embedding"] for item in ordered]
                if len(vectors) != len(window):
                    raise EmbeddingError(f"réponse incomplète: {len(vectors)} vecteurs pour {len(window)} textes")
                dim = self.settings.embedding_dim
                for vec in vectors:
                    if len(vec) != dim:
                        raise EmbeddingError(f"dimension inattendue {len(vec)} (attendu {dim})")
                out.extend(vectors)
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text], input_type="query")[0]

    def try_embed_query(self, text: str) -> list[float] | None:
        """Variante non bloquante pour la recherche : renvoie None au lieu de lever."""
        try:
            return self.embed_query(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("embed_query indisponible, repli lexical: %s", type(exc).__name__)
            return None

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# On cible un modèle instruct NON-raisonnant (cf. config.extraction_model). Le système
# impose une sortie JSON pure ; le parseur reste robuste par sécurité.
_SYSTEM = "Tu es un extracteur de connaissances. Tu réponds UNIQUEMENT par du JSON valide, sans aucun texte ni explication autour."

_PROMPT = """Tu es un extracteur de connaissances pour une mémoire-graphe (MemGraphRAG).
À partir du TEXTE ci-dessous, extrais :
1) les entités nommées (personnes, organisations, lieux, concepts, produits, dates) ;
2) les faits sous forme de triplets (sujet, prédicat, objet) EXPLICITEMENT soutenus par le texte.

Règles strictes :
- Reste fidèle au texte : n'invente aucun fait, aucune entité absente.
- Prédicats courts, en minuscules (ex: "utilise", "est_situé_à", "a_pour_rôle").
- Conserve la langue du texte.
- Si rien d'extractible, renvoie des listes vides.

Réponds UNIQUEMENT par un JSON valide, sans texte autour :
{"entities":[{"name":"...","type":"person|org|place|concept|product|date|other"}],
 "facts":[{"subject":"...","predicate":"...","object":"...","confidence":0.0}]}

TEXTE :
\"\"\"
%s
\"\"\""""


class ExtractionError(RuntimeError):
    pass


def _coerce_json(raw: str) -> dict[str, Any]:
    """Parse JSON même si le modèle a ajouté du raisonnement/texte/fences autour.

    Tolère : texte avant, plusieurs objets, données en trop après (raw_decode s'arrête
    à la fin du premier objet complet). On retient le premier objet portant entities/facts.
    """
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(raw, idx)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict) and ("entities" in obj or "facts" in obj):
            return obj
    raise ValueError("aucun objet JSON entities/facts trouvé dans la réponse")


class ExtractionService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _model(self) -> str:
        return self.settings.extraction_model or self.settings.llm_model

    def configured(self) -> bool:
        s = self.settings
        return bool(self._model() and s.llm_base_url and s.llm_api_key.get_secret_value())

    def extract(self, text: str, max_tokens: int = 3000) -> dict[str, list[dict[str, Any]]]:
        """Extrait {entities:[...], facts:[...]} d'un texte. Lève ExtractionError en cas d'échec."""
        if not self.configured():
            raise ExtractionError("LLM provider non configuré (llm_model/base_url/api_key manquant)")
        text = (text or "").strip()
        if not text:
            return {"entities": [], "facts": []}

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key.get_secret_value()}",
            "Accept": "application/json",
        }
        body = {
            "model": self._model(),
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _PROMPT % text[:6000]},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{self.settings.llm_base_url.rstrip('/')}/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            raise ExtractionError(f"HTTP {exc.response.status_code} du LLM") from exc
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"appel LLM échoué: {type(exc).__name__}") from exc

        try:
            data = _coerce_json(content)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"réponse LLM non parsable en JSON: {type(exc).__name__}") from exc

        entities = [e for e in data.get("entities", []) if isinstance(e, dict) and e.get("name")]
        facts = [
            f for f in data.get("facts", [])
            if isinstance(f, dict) and f.get("subject") and f.get("predicate") and f.get("object")
        ]
        return {"entities": entities, "facts": facts}

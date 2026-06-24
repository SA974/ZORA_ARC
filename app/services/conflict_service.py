"""Détection et résolution de conflits MemGraphRAG multi-types (arXiv:2606.00610).

Types de conflits :
  1. Temporel : sim > threshold, ordonnancement chronologique (le plus récent prime).
  2. Mutuellement exclusif : même sujet+prédicat, objets lexicalement/sémantiquement contradictoires
     (ex. "is Y" vs "is NOT Y", "Paris" vs "not Paris").
  3. Granularité : l'un des faits généralise l'autre (ex. "X lives in Paris" vs "X lives in France").

Résolution : comparaison des passages de provenance (evidence-driven) — quelle preuve est
plus crédible/détaillée/récente ? La décision de supersession dépend de la qualité de la
provenance, pas juste du temps.
"""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from app.db import get_connection

logger = logging.getLogger(__name__)

# Seuils
CONFLICT_SIM_THRESHOLD = 0.80  # similarité cosinus pour temporel + granularité
NEGATION_PATTERNS = (
    r"\bnot\b",
    r"\bno\b",
    r"\bne\b",
    r"\bn[\'`]a\b",  # French "n'a"
    r"\baucun",
)

FREQUENCY_THRESHOLD = 3  # un schéma devient stable après 3 utilisations


class ConflictType(str, Enum):
    TEMPORAL = "temporal"
    MUTUALLY_EXCLUSIVE = "mutually_exclusive"
    GRANULARITY = "granularity"


def _has_negation(text: str) -> bool:
    """Détecte si le texte contient une négation."""
    return any(re.search(pat, text.lower()) for pat in NEGATION_PATTERNS)


def _is_contradict_object(obj1: str, obj2: str) -> bool:
    """Teste si obj1 et obj2 sont lexicalement/sémantiquement contradictoires.

    Ex. "Y" vs "NOT Y", "yes" vs "no", "alive" vs "dead".
    """
    neg1, neg2 = _has_negation(obj1), _has_negation(obj2)
    if neg1 and not neg2:
        # obj1 a une négation, obj2 non : potentiellement contradictoires
        base1 = re.sub(r"\b(not|no|n[\'`a])\s+", "", obj1.lower())
        base2 = obj2.lower()
        return base1.strip() and base1 in base2 or base2 in base1
    elif neg2 and not neg1:
        base1 = obj1.lower()
        base2 = re.sub(r"\b(not|no|n[\'`a])\s+", "", obj2.lower())
        return base2.strip() and base2 in base1 or base1 in base2
    return False


def _compare_evidence_quality(prov1: str, prov2: str) -> tuple[str, float]:
    """Compare deux passages de provenance. Retourne (meilleur_id, confiance).

    Critères : longueur, densité lexicale, recency (si disponible).
    Ici simplifié : le passage plus long est supposé plus détaillé.
    """
    len1, len2 = len(prov1), len(prov2)
    if len1 == len2:
        return ("tie", 0.5)
    if len1 > len2:
        return ("first", min(0.95, 0.5 + (len1 / (len1 + len2)) * 0.45))
    return ("second", min(0.95, 0.5 + (len2 / (len1 + len2)) * 0.45))


class ConflictService:
    def detect_conflicts(self, fact_id: str) -> dict[str, Any]:
        """Détecte tous les types de conflits pour un fait donné.

        Retourne une liste de conflits avec type, fact_id, evidence_comparison.
        """
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select id, subject, predicate, object_value, embedding, provenance_text, observed_at "
                "from memgraph.mem_facts where id = %s",
                (fact_id,),
            )
            f = cur.fetchone()
            if not f:
                raise KeyError(f"fait introuvable: {fact_id}")

            conflicts = []

            # --- Type 1 : Temporel ---
            conflicts.extend(self._detect_temporal(cur, f))

            # --- Type 2 : Mutuellement exclusif ---
            conflicts.extend(self._detect_mutually_exclusive(cur, f))

            # --- Type 3 : Granularité ---
            conflicts.extend(self._detect_granularity(cur, f))

        return {"fact_id": fact_id, "conflicts": conflicts}

    def _detect_temporal(self, cur, fact: dict) -> list[dict[str, Any]]:
        """Conflits temporels : sim > threshold, objets différents."""
        conflicts = []
        has_emb = fact["embedding"] is not None
        if not has_emb:
            return conflicts

        cur.execute(
            """
            select id, object_value, observed_at, provenance_text,
                   (embedding <=> %s) as distance
            from memgraph.mem_facts
            where id <> %s and superseded_by is null
              and lower(subject) = lower(%s) and lower(predicate) = lower(%s)
              and lower(object_value) <> lower(%s) and embedding is not null
            order by distance asc limit 5
            """,
            (fact["embedding"], fact["id"], fact["subject"], fact["predicate"], fact["object_value"]),
        )
        for c in cur.fetchall():
            sim = round(1.0 - float(c["distance"]), 4)
            if sim < CONFLICT_SIM_THRESHOLD:
                continue
            better, conf = _compare_evidence_quality(fact["provenance_text"], c["provenance_text"])
            conflicts.append({
                "conflicting_fact_id": str(c["id"]),
                "conflict_type": ConflictType.TEMPORAL.value,
                "evidence_comparison": f"sim={sim}, provenance: {better} (conf={conf:.2f})",
            })
        return conflicts

    def _detect_mutually_exclusive(self, cur, fact: dict) -> list[dict[str, Any]]:
        """Conflits mutuellement exclusifs : même sujet+prédicat, objets contradictoires."""
        conflicts = []
        cur.execute(
            """
            select id, object_value, provenance_text
            from memgraph.mem_facts
            where id <> %s and superseded_by is null
              and lower(subject) = lower(%s) and lower(predicate) = lower(%s)
              and lower(object_value) <> lower(%s)
            limit 10
            """,
            (fact["id"], fact["subject"], fact["predicate"], fact["object_value"]),
        )
        for c in cur.fetchall():
            if not _is_contradict_object(fact["object_value"], c["object_value"]):
                continue
            better, conf = _compare_evidence_quality(fact["provenance_text"], c["provenance_text"])
            conflicts.append({
                "conflicting_fact_id": str(c["id"]),
                "conflict_type": ConflictType.MUTUALLY_EXCLUSIVE.value,
                "evidence_comparison": f"objet contradictoire, provenance: {better} (conf={conf:.2f})",
            })
        return conflicts

    def _detect_granularity(self, cur, fact: dict) -> list[dict[str, Any]]:
        """Conflits de granularité : l'un généralise l'autre (ex. Paris ⊂ France).

        Heuristique simple : substring matching sur les objets + similarité embedding.
        """
        conflicts = []
        has_emb = fact["embedding"] is not None
        if not has_emb:
            return conflicts

        cur.execute(
            """
            select id, object_value, provenance_text,
                   (1.0 - (embedding <=> %s::vector)) as similarity
            from memgraph.mem_facts
            where id <> %s and superseded_by is null
              and lower(subject) = lower(%s) and lower(predicate) = lower(%s)
              and embedding is not null and lower(object_value) <> lower(%s)
            order by embedding <=> %s::vector asc limit 5
            """,
            (fact["embedding"], fact["id"], fact["subject"], fact["predicate"],
             fact["object_value"], fact["embedding"]),
        )
        for c in cur.fetchall():
            sim = round(float(c["similarity"]), 4)
            if sim < CONFLICT_SIM_THRESHOLD:
                continue
            obj_our = fact["object_value"].lower()
            obj_other = c["object_value"].lower()
            if obj_our in obj_other or obj_other in obj_our:
                better, conf = _compare_evidence_quality(fact["provenance_text"], c["provenance_text"])
                conflicts.append({
                    "conflicting_fact_id": str(c["id"]),
                    "conflict_type": ConflictType.GRANULARITY.value,
                    "evidence_comparison": f"inclusion: {obj_our} ⊂ {obj_other}, provenance: {better} (conf={conf:.2f})",
                })
        return conflicts

    def record_conflict_resolution(
        self, fact_id: str, conflicting_fact_id: str, conflict_type: str,
        evidence_comparison: str, supersede: bool = False
    ) -> dict[str, Any]:
        """Enregistre la résolution d'un conflit. Optionnellement supersède le conflicting_fact."""
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into memgraph.mem_conflicts
                        (fact_id, conflicting_fact_id, conflict_type_enum, evidence_comparison, status, resolution_text)
                        values (%s, %s, %s, %s, 'resolved', %s)
                        returning id
                        """,
                        (fact_id, conflicting_fact_id, conflict_type, evidence_comparison,
                         f"supersede={supersede}" if supersede else "keep_both"),
                    )
                    conf_id = cur.fetchone()["id"]
                    if supersede:
                        cur.execute(
                            "update memgraph.mem_facts set superseded_by = %s where id = %s",
                            (fact_id, conflicting_fact_id),
                        )
        return {"ok": True, "conflict_id": str(conf_id), "superseded": supersede}

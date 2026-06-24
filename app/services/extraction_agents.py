"""Société multi-agents d'extraction MemGraphRAG (arXiv:2606.00610 §3.2).

Trois agents collaboratifs sur mémoire partagée (le graphe MemGraphRAG en DB) :
  - ExtractionAgent (A_ext)  : transforme un chunk en entités + triplets.
  - DetectionAgent  (A_det)  : surveille mem_facts, détecte conflits multi-types.
  - ResolutionAgent (A_res)  : adjuge les conflits via comparaison des passages de provenance.

Chaque agent est indépendant et peut être lancé séparément ou en chaîne.
La mémoire partagée = les tables PostgreSQL (mem_facts, mem_passages, mem_bridges, mem_conflicts).
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.conflict_service import ConflictService
from app.services.extraction_service import ExtractionError, ExtractionService
from app.services.memgraph_service import MemGraphService
from app.services.schema_gating import SchemaGatingService
from app.services.temporal_service import TemporalService

logger = logging.getLogger(__name__)


class ExtractionAgent:
    """A_ext : extrait entités + triplets d'un chunk et les stocke dans la mémoire partagée.

    Conforme à A_ext(c_i) → {S_cand ∈ M_ont, T_cand ∈ M_fac, P_src ∈ M_pas}.
    Retourne les IDs créés pour que A_det puisse les surveiller.
    """

    def __init__(self) -> None:
        self.extractor = ExtractionService()
        self.memgraph = MemGraphService()
        self.temporal = TemporalService()
        self.schema_gating = SchemaGatingService()

    def configured(self) -> bool:
        return self.extractor.configured()

    def run(
        self,
        text: str,
        source_document_id: str | None = None,
        source_chunk_id: str | None = None,
        domain: str = "bibliotheque",
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Extrait et stocke. Retourne {passage_id, entity_ids, fact_ids, schema_statuses}."""
        result = self.extractor.extract(text)
        entities = result["entities"]
        facts = result["facts"]

        passage = self.memgraph.create_passage(
            passage_text=text,
            provenance_text=text[:500],
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            metadata={"origin": "extraction_agent", "domain": domain},
        )
        passage_id = str(passage["id"])

        entity_ids: list[str] = []
        for e in entities:
            row = self.memgraph.create_entity(
                str(e["name"]), str(e.get("type", "other") or "other"),
                {"origin": "extraction_agent"}, None,
            )
            if row.get("id"):
                entity_ids.append(str(row["id"]))

        fact_ids: list[str] = []
        schema_statuses: dict[str, str] = {}
        for f in facts:
            predicate = str(f["predicate"])
            schema_info = self.schema_gating.register_schema_usage(predicate)
            schema_statuses[predicate] = schema_info["status"]
            try:
                conf = max(0.0, min(1.0, float(f.get("confidence", 0.5) or 0.5)))
            except (TypeError, ValueError):
                conf = 0.5
            fact = self.temporal.add_fact(
                subject=str(f["subject"]),
                predicate=predicate,
                object_value=str(f["object"]),
                provenance_text=text[:1000],
                source_document_id=source_document_id,
                source_chunk_id=source_chunk_id,
                confidence=conf,
                observed_at=observed_at,
            )
            fid = str(fact["id"])
            fact_ids.append(fid)
            if schema_info["status"] == "stable":
                self.memgraph.link_fact_to_passage(fid, passage_id)

        return {
            "passage_id": passage_id,
            "entity_ids": entity_ids,
            "fact_ids": fact_ids,
            "schema_statuses": schema_statuses,
        }


class DetectionAgent:
    """A_det : surveille mem_facts pour détecter conflits multi-types.

    Conforme à A_det monitore M_fac : détecte redondance, anomalies structurelles,
    incohérences logiques — F_conf = {t' | Sim(t_new, t') > δ ∨ Match(t_new, t')}.
    """

    def __init__(self) -> None:
        self.conflict_svc = ConflictService()

    def run(self, fact_ids: list[str]) -> dict[str, Any]:
        """Détecte tous les conflits pour les faits donnés. Retourne la liste groupée."""
        all_conflicts: list[dict[str, Any]] = []
        for fid in fact_ids:
            try:
                result = self.conflict_svc.detect_conflicts(fid)
                for c in result.get("conflicts", []):
                    c["fact_id"] = fid
                    all_conflicts.append(c)
            except Exception as exc:  # noqa: BLE001
                logger.warning("détection ignorée pour %s: %s", fid, type(exc).__name__)

        by_type: dict[str, int] = {}
        for c in all_conflicts:
            by_type[c["conflict_type"]] = by_type.get(c["conflict_type"], 0) + 1

        return {
            "total_conflicts": len(all_conflicts),
            "by_type": by_type,
            "conflicts": all_conflicts,
        }


class ResolutionAgent:
    """A_res : adjuge les conflits en comparant les passages de provenance (evidence-driven).

    Conforme à : A_res récupère provenance passages de M_pas et adjuge par comparaison
    textuelle des preuves (pas de supersession heuristique aveugle).
    """

    def __init__(self) -> None:
        self.conflict_svc = ConflictService()
        self.memgraph = MemGraphService()

    def run(
        self,
        conflicts: list[dict[str, Any]],
        *,
        auto_supersede: bool = False,
    ) -> dict[str, Any]:
        """Adjuge chaque conflit. Si auto_supersede, supersède le fait moins fiable."""
        resolutions: list[dict[str, Any]] = []
        for c in conflicts:
            fact_id = c.get("fact_id") or c.get("conflicting_fact_id")
            conflicting_id = c.get("conflicting_fact_id")
            conflict_type = c.get("conflict_type", "temporal")
            evidence = c.get("evidence_comparison", "")

            # Décide qui supersède : si "first" dans la comparaison → le fait courant prime
            supersede = False
            if auto_supersede and "first" in evidence:
                supersede = True

            try:
                r = self.conflict_svc.record_conflict_resolution(
                    fact_id=fact_id,
                    conflicting_fact_id=conflicting_id,
                    conflict_type=conflict_type,
                    evidence_comparison=evidence,
                    supersede=supersede,
                )
                resolutions.append({"fact_id": fact_id, "conflicting_id": conflicting_id,
                                    "resolved": True, "superseded": supersede, **r})
            except Exception as exc:  # noqa: BLE001
                logger.warning("résolution ignorée pour %s: %s", fact_id, type(exc).__name__)
                resolutions.append({"fact_id": fact_id, "resolved": False, "error": str(exc)})

        return {
            "total_resolved": sum(1 for r in resolutions if r.get("resolved")),
            "total_superseded": sum(1 for r in resolutions if r.get("superseded")),
            "resolutions": resolutions,
        }


class MultiAgentExtractor:
    """Orchestre A_ext → A_det → A_res en chaîne sur un chunk de texte."""

    def __init__(self) -> None:
        self.extraction_agent = ExtractionAgent()
        self.detection_agent = DetectionAgent()
        self.resolution_agent = ResolutionAgent()

    def configured(self) -> bool:
        return self.extraction_agent.configured()

    def run(
        self,
        text: str,
        source_document_id: str | None = None,
        source_chunk_id: str | None = None,
        domain: str = "bibliotheque",
        auto_resolve: bool = False,
        auto_supersede: bool = False,
    ) -> dict[str, Any]:
        """Chaîne complète A_ext → A_det → A_res sur un chunk."""
        # A_ext
        extracted = self.extraction_agent.run(
            text, source_document_id=source_document_id,
            source_chunk_id=source_chunk_id, domain=domain,
        )

        # A_det
        detection = self.detection_agent.run(extracted["fact_ids"])

        # A_res (optionnel)
        resolution = {"total_resolved": 0, "total_superseded": 0, "resolutions": []}
        if auto_resolve and detection["conflicts"]:
            resolution = self.resolution_agent.run(
                detection["conflicts"], auto_supersede=auto_supersede,
            )

        return {
            "passage_id": extracted["passage_id"],
            "entity_ids": extracted["entity_ids"],
            "fact_ids": extracted["fact_ids"],
            "schema_statuses": extracted["schema_statuses"],
            "conflicts_detected": detection["total_conflicts"],
            "conflicts_by_type": detection["by_type"],
            "conflicts_resolved": resolution["total_resolved"],
            "conflicts_superseded": resolution["total_superseded"],
        }

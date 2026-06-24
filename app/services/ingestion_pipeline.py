from __future__ import annotations

import logging
from typing import Any

from app.services.embedding_service import EmbeddingService, to_pgvector
from app.services.extraction_service import ExtractionService
from app.services.memgraph_service import MemGraphService
from app.services.temporal_service import TemporalService

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Chaîne MemGraphRAG : texte -> passage -> entités -> faits (triplets) -> bridges -> (conflits).

    detect_conflicts est OPT-IN : la supersession temporelle automatique peut écraser à tort
    des faits multivalués. On préfère stocker, puis lancer la détection explicitement.
    """

    def __init__(self) -> None:
        self.extractor = ExtractionService()
        self.memgraph = MemGraphService()
        self.temporal = TemporalService()
        self.embedder = EmbeddingService()

    def configured(self) -> bool:
        return self.extractor.configured()

    def extract_and_store(
        self,
        text: str,
        source_document_id: str | None = None,
        source_chunk_id: str | None = None,
        observed_at: str | None = None,
        detect_conflicts: bool = False,
        passage_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.extractor.extract(text)
        entities = result["entities"]
        facts = result["facts"]

        meta = {"origin": "memgraphrag_extraction"}
        if passage_metadata:
            meta.update(passage_metadata)
        passage = self.memgraph.create_passage(
            passage_text=text,
            provenance_text=text[:500],
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            metadata=meta,
        )
        passage_id = str(passage["id"])

        # Entités : un seul appel d'embedding pour tous les noms.
        entity_ids: list[str] = []
        if entities:
            names = [str(e["name"]) for e in entities]
            embs = None
            if self.embedder.configured():
                try:
                    embs = self.embedder.embed_texts(names, "passage")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("entités sans embedding: %s", type(exc).__name__)
            for i, e in enumerate(entities):
                lit = to_pgvector(embs[i]) if embs is not None else None
                row = self.memgraph.create_entity(
                    str(e["name"]), str(e.get("type", "other") or "other"), {"origin": "extraction"}, lit
                )
                if row.get("id"):
                    entity_ids.append(str(row["id"]))

        # Faits : add_fact gère embedding + champs temporels.
        fact_ids: list[str] = []
        conflicts: list[dict[str, Any]] = []
        for f in facts:
            try:
                conf = float(f.get("confidence", 0.5) or 0.5)
            except (TypeError, ValueError):
                conf = 0.5
            conf = max(0.0, min(1.0, conf))
            fact = self.temporal.add_fact(
                subject=str(f["subject"]),
                predicate=str(f["predicate"]),
                object_value=str(f["object"]),
                provenance_text=text[:1000],
                source_document_id=source_document_id,
                source_chunk_id=source_chunk_id,
                confidence=conf,
                observed_at=observed_at,
            )
            fid = str(fact["id"])
            fact_ids.append(fid)
            self.memgraph.link_fact_to_passage(fid, passage_id)
            if detect_conflicts:
                try:
                    conflicts.extend(self.temporal.detect_temporal_conflict(fid).get("conflicts", []))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("détection de conflit ignorée pour %s: %s", fid, type(exc).__name__)

        return {
            "ok": True,
            "passage_id": passage_id,
            "entities": len(entity_ids),
            "facts": len(fact_ids),
            "fact_ids": fact_ids,
            "conflicts": conflicts,
        }

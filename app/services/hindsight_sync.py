from __future__ import annotations

import logging
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import Settings, get_settings
from app.db import get_connection
from app.services.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

# En dessous de cette longueur, les souvenirs Hindsight (ex: "session_du: 2026-05-22")
# ne produisent pas de triplets utiles : on les saute par défaut.
DEFAULT_MIN_LEN = 25


class HindsightGraphSync:
    """Synchronise la mémoire agentique Hindsight (hindsight_hermes.facts) vers le graphe
    MemGraphRAG (rag_arc). Idempotent : chaque passage est tagué hindsight_fact_id ;
    les souvenirs déjà synchronisés sont sautés (les deux bases étant distinctes, le diff
    se fait en Python).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.pipeline = IngestionPipeline()

    def configured(self) -> bool:
        return bool(self.settings.hindsight_database_url.get_secret_value()) and self.pipeline.configured()

    def _already_synced_ids(self) -> set[str]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select metadata->>'hindsight_fact_id' as hid from memgraph.mem_passages where metadata ? 'hindsight_fact_id'"
            )
            return {r["hid"] for r in cur.fetchall() if r["hid"]}

    def pending_facts(self, min_len: int = DEFAULT_MIN_LEN, limit: int = 0) -> list[dict[str, Any]]:
        dsn = self.settings.hindsight_database_url.get_secret_value()
        with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, content, fact_type, created_at
                from facts
                where length(trim(content)) >= %s
                order by created_at asc
                """,
                (min_len,),
            )
            rows = [dict(r) for r in cur.fetchall()]
        synced = self._already_synced_ids()
        pending = [r for r in rows if str(r["id"]) not in synced]
        return pending[:limit] if limit else pending

    def sync(self, min_len: int = DEFAULT_MIN_LEN, limit: int = 0, detect_conflicts: bool = False) -> dict[str, Any]:
        if not self.configured():
            return {"ok": False, "error": "Hindsight et/ou LLM non configurés"}
        pending = self.pending_facts(min_len=min_len, limit=limit)
        processed = entities = facts = conflicts = errors = 0
        for f in pending:
            try:
                res = self.pipeline.extract_and_store(
                    f["content"],
                    observed_at=f["created_at"].isoformat() if f.get("created_at") else None,
                    detect_conflicts=detect_conflicts,
                    passage_metadata={"source": "hindsight", "hindsight_fact_id": str(f["id"]),
                                      "fact_type": f.get("fact_type")},
                )
                processed += 1
                entities += res["entities"]
                facts += res["facts"]
                conflicts += len(res["conflicts"])
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning("sync hindsight fact %s ignoré: %s", f["id"], type(exc).__name__)
        return {
            "ok": True,
            "candidates": len(pending),
            "processed": processed,
            "entities": entities,
            "facts": facts,
            "conflicts": conflicts,
            "errors": errors,
        }

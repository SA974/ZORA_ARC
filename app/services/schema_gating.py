"""Gating de schéma par fréquence (arXiv:2606.00610 — MemGraphRAG).

Un schéma (ontologie) commence en `candidate` et devient `stable` une fois qu'un nombre seuil
(FREQUENCY_THRESHOLD) de faits l'ont utilisé. Seuls les faits à schéma `stable` sont admis
dans le graphe MemGraphRAG (anti-hallucination, filtrage des patterns rares/bruyants).
"""
from __future__ import annotations

import logging
from typing import Any

from app.db import get_connection

logger = logging.getLogger(__name__)

FREQUENCY_THRESHOLD = 3


class SchemaGatingService:
    def register_schema_usage(self, schema_name: str) -> dict[str, Any]:
        """Enregistre l'utilisation d'un schéma. Le promeut en `stable` si le seuil est atteint."""
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # Incrémenter ou créer
                    cur.execute(
                        """
                        insert into memgraph.mem_schemas (name, status, frequency_count)
                        values (%s, 'candidate', 1)
                        on conflict (name)
                        do update set frequency_count = mem_schemas.frequency_count + 1
                        returning id, name, status, frequency_count
                        """,
                        (schema_name,),
                    )
                    row = cur.fetchone()
                    schema_id = str(row["id"])
                    status = row["status"]
                    freq = row["frequency_count"]

                    # Promotion candidate → stable au seuil
                    if status == "candidate" and freq >= FREQUENCY_THRESHOLD:
                        cur.execute(
                            "update memgraph.mem_schemas set status = 'stable' where id = %s returning status",
                            (schema_id,),
                        )
                        new_status = cur.fetchone()["status"]
                        logger.info(f"schéma {schema_name!r} promu candidate→stable (freq={freq})")
                        return {"schema_id": schema_id, "schema_name": schema_name,
                                "frequency": freq, "promoted": True, "status": new_status}

        return {"schema_id": schema_id, "schema_name": schema_name,
                "frequency": freq, "promoted": False, "status": status}

    def is_schema_stable(self, schema_name: str) -> bool:
        """Teste si un schéma est stable (admis au graphe)."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("select status from memgraph.mem_schemas where name = %s", (schema_name,))
            row = cur.fetchone()
            if not row:
                return False
            return row["status"] == "stable"

    def get_schema_info(self, schema_name: str) -> dict[str, Any] | None:
        """Retourne le statut et fréquence d'un schéma."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select id, name, status, frequency_count, created_at from memgraph.mem_schemas where name = %s",
                (schema_name,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": str(row["id"]),
                "name": row["name"],
                "status": row["status"],
                "frequency": row["frequency_count"],
                "threshold": FREQUENCY_THRESHOLD,
                "progress": f"{row['frequency_count']}/{FREQUENCY_THRESHOLD}",
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }

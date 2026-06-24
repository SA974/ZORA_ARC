from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from app.db import get_connection


class MemGraphService:
    def create_entity(
        self,
        name: str,
        entity_type: str = "unknown",
        metadata: dict[str, Any] | None = None,
        embedding: str | None = None,
    ) -> dict[str, Any]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into memgraph.mem_entities(name, entity_type, metadata, embedding)
                values (%s, %s, %s::jsonb, %s::vector)
                on conflict (name, entity_type) do update set
                  metadata = memgraph.mem_entities.metadata || excluded.metadata,
                  embedding = coalesce(excluded.embedding, memgraph.mem_entities.embedding)
                returning id, name, entity_type
                """,
                (name, entity_type, Jsonb(metadata or {}), embedding),
            )
            row = cur.fetchone() or {}
            conn.commit()
            return dict(row)

    def create_passage(
        self,
        passage_text: str,
        provenance_text: str,
        source_document_id: str | None = None,
        source_chunk_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into memgraph.mem_passages(
                  source_document_id, source_chunk_id, passage_text, provenance_text, status, metadata
                )
                values (%s, %s, %s, %s, 'active', %s::jsonb)
                returning id
                """,
                (source_document_id, source_chunk_id, passage_text, provenance_text, Jsonb(metadata or {})),
            )
            row = cur.fetchone() or {}
            conn.commit()
            return dict(row)

    def create_fact(
        self,
        subject: str,
        predicate: str,
        object_value: str,
        provenance_text: str,
        source_document_id: str | None = None,
        source_chunk_id: str | None = None,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into memgraph.mem_facts(
                  subject, predicate, object_value, provenance_text,
                  source_document_id, source_chunk_id, confidence, status
                )
                values (%s, %s, %s, %s, %s, %s, %s, 'pending')
                returning id, subject, predicate, object_value, status
                """,
                (subject, predicate, object_value, provenance_text, source_document_id, source_chunk_id, confidence),
            )
            row = cur.fetchone() or {}
            conn.commit()
            return dict(row)

    def link_fact_to_passage(self, fact_id: str, passage_id: str) -> dict[str, Any]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into memgraph.mem_bridges(left_type, left_id, right_type, right_id, relation_type)
                values ('fact', %s, 'passage', %s, 'supported_by')
                returning id, relation_type
                """,
                (fact_id, passage_id),
            )
            row = cur.fetchone() or {}
            conn.commit()
            return dict(row)

    def detect_conflict_placeholder(self, fact_id: str) -> dict[str, Any]:
        return {"ok": True, "fact_id": fact_id, "conflicts": [], "note": "LLM/logic conflict detection not configured yet"}

    def resolve_conflict_placeholder(self, conflict_id: str) -> dict[str, Any]:
        return {"ok": True, "conflict_id": conflict_id, "note": "Manual conflict resolution workflow pending"}

    def get_facts_for_query(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    select id, subject, predicate, object_value, provenance_text, confidence, status
                    from memgraph.mem_facts
                    where subject ilike %s or predicate ilike %s or object_value ilike %s or provenance_text ilike %s
                    order by confidence desc, created_at desc
                    limit %s
                    """,
                    tuple([f"%{query}%"] * 4 + [limit]),
                )
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            return [{"warning": f"memgraph query unavailable: {exc}"}]

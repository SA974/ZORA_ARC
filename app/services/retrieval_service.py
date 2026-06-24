from __future__ import annotations

from typing import Any

from app.models.schemas import ContextBundle
from app.services.embedding_service import EmbeddingService, to_pgvector
from app.services.hmem_router import HMemRouter
from app.services.memgraph_service import MemGraphService
from app.services.temporal_service import TemporalService


class RetrievalService:
    def __init__(self) -> None:
        self.router = HMemRouter()
        self.memgraph = MemGraphService()
        self.temporal = TemporalService()
        self.embedder = EmbeddingService()

    def lexical_chunks(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        from app.db import get_connection

        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    select c.id, c.document_id, c.ordinal, c.content, d.title, d.source_uri
                    from zora.chunks c
                    join zora.documents d on d.id = c.document_id
                    where c.content ilike %s or d.title ilike %s
                    order by c.created_at desc
                    limit %s
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                rows = [dict(row) for row in cur.fetchall()]
                for row in rows:
                    row["retrieval_mode"] = "lexical"
                return rows
        except Exception as exc:  # noqa: BLE001
            return [{"warning": f"lexical retrieval unavailable: {exc}"}]

    def semantic_chunks(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Recherche vectorielle (cosinus) sur zora.chunks. Repli silencieux si embeddings indisponibles."""
        qvec = self.embedder.try_embed_query(query)
        if qvec is None:
            return []
        from app.db import get_connection

        literal = to_pgvector(qvec)
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    select c.id, c.document_id, c.ordinal, c.content, d.title, d.source_uri,
                           (c.embedding <=> %s::vector) as distance
                    from zora.chunks c
                    join zora.documents d on d.id = c.document_id
                    where c.embedding is not null
                    order by c.embedding <=> %s::vector
                    limit %s
                    """,
                    (literal, literal, limit),
                )
                rows = [dict(row) for row in cur.fetchall()]
                for row in rows:
                    dist = float(row.pop("distance"))
                    row["score"] = round(1.0 - dist, 4)  # similarité cosinus
                    row["retrieval_mode"] = "semantic"
                return rows
        except Exception as exc:  # noqa: BLE001
            return [{"warning": f"semantic retrieval unavailable: {exc}"}]

    def hybrid_chunks(self, query: str, limit: int = 8) -> tuple[list[dict[str, Any]], list[str]]:
        """Fusion sémantique (prioritaire) + lexical, dédupliquée par chunk id."""
        warnings: list[str] = []
        semantic = self.semantic_chunks(query, limit=limit)
        lexical = self.lexical_chunks(query, limit=limit)

        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in semantic + lexical:
            if "warning" in row:
                warnings.append(row["warning"])
                continue
            cid = str(row.get("id"))
            if cid in seen:
                continue
            seen.add(cid)
            merged.append(row)
            if len(merged) >= limit:
                break
        return merged, warnings

    def build_context_bundle(
        self,
        query: str,
        hindsight_context: list[dict[str, Any]] | None = None,
        limit: int = 8,
    ) -> ContextBundle:
        route_paths = self.router.route_query(query)
        facts = self.temporal.active_facts_for_query(query, limit=limit)
        self.temporal.touch_access([str(f["id"]) for f in facts if "id" in f])
        passages, warnings = self.hybrid_chunks(query, limit=limit)
        warnings.extend(f["warning"] for f in facts if "warning" in f)
        citations = []
        for passage in passages:
            if "id" in passage:
                citations.append(
                    {
                        "chunk_id": str(passage["id"]),
                        "document_id": str(passage["document_id"]),
                        "title": passage.get("title"),
                        "source_uri": passage.get("source_uri"),
                        "retrieval_mode": passage.get("retrieval_mode"),
                        "score": passage.get("score"),
                    }
                )
        return ContextBundle(
            memories=hindsight_context or [],
            route_paths=route_paths,
            facts=facts,
            passages=passages,
            citations=citations,
            warnings=warnings,
        )

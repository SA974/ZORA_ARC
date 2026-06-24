"""Retrieval hiérarchique H-MEM avec scoring.

Routage descendant (domain -> theme -> faits) puis sélection des meilleurs nœuds par un
score combiné : similarité vectorielle (768D) + salience temporelle (décroissance H-MEM)
+ poids d'arête. Repli lexical si l'embedding de requête est indisponible.
"""
from __future__ import annotations

import logging
from typing import Any

from app.db import get_connection
from app.services.embedding_service import EmbeddingService, to_pgvector
from app.services.hmem_builder import _layer_id
from app.services.hmem_router import HMemRouter
from app.services.memgraph_service import MemGraphService

logger = logging.getLogger(__name__)


def score_candidate(
    similarity: float, salience: float, edge_weight: float = 1.0,
    *, alpha: float = 0.6, beta: float = 0.3, gamma: float = 0.1,
) -> float:
    """Score combiné, borné [0,1]. alpha+beta+gamma = 1 par convention."""
    s = alpha * float(similarity) + beta * float(salience) + gamma * float(edge_weight)
    return max(0.0, min(1.0, s))


def _passages_for_fact(cur, fact_id: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select distinct p.id, p.passage_text, p.provenance_text
        from hmem.memory_nodes fn
        join hmem.memory_edges e on e.source_node_id = fn.id and e.edge_type = 'evidences'
        join hmem.memory_nodes pn on pn.id = e.target_node_id
        join memgraph.mem_passages p
          on pn.target_schema = 'memgraph' and pn.target_table = 'mem_passages' and pn.target_id = p.id
        where fn.target_table = 'mem_facts' and fn.target_id = %s
        """,
        (fact_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def hmem_retrieve(query: str, limit: int = 8) -> dict[str, Any]:
    """Retrieval H-MEM. Retourne routing_path + faits scorés + passages-preuves."""
    routing_path = HMemRouter().route_query(query)
    qvec = EmbeddingService().try_embed_query(query)

    if qvec is None:
        # Repli lexical : pas d'embedding de requête disponible.
        facts = MemGraphService().get_facts_for_query(query, limit=limit)
        return {"mode": "lexical_fallback", "routing_path": routing_path,
                "query_embedded": False, "facts": facts, "passages": []}

    lit = to_pgvector(qvec)
    fact_layer = _layer_id("fact")
    facts_out: list[dict[str, Any]] = []
    passages_out: dict[str, dict[str, Any]] = {}

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select f.id, f.subject, f.predicate, f.object_value,
                   1 - (f.embedding <=> %s::vector) as similarity,
                   coalesce(vaf.salience_now, f.salience, 1.0) as salience
            from hmem.memory_nodes n
            join memgraph.mem_facts f
              on n.target_schema = 'memgraph' and n.target_table = 'mem_facts' and n.target_id = f.id
            left join memgraph.v_active_facts vaf on vaf.id = f.id
            where n.layer_id = %s and f.embedding is not null
            order by f.embedding <=> %s::vector
            limit %s
            """,
            (lit, fact_layer, lit, limit),
        )
        rows = cur.fetchall()
        for r in rows:
            score = score_candidate(r["similarity"], r["salience"])
            facts_out.append({
                "id": str(r["id"]), "subject": r["subject"], "predicate": r["predicate"],
                "object": r["object_value"], "similarity": round(float(r["similarity"]), 4),
                "salience": round(float(r["salience"]), 4), "score": round(score, 4),
            })
            for p in _passages_for_fact(cur, str(r["id"])):
                passages_out.setdefault(str(p["id"]), {
                    "id": str(p["id"]), "passage_text": p["passage_text"],
                    "provenance_text": p["provenance_text"],
                })

    facts_out.sort(key=lambda x: x["score"], reverse=True)
    return {"mode": "hierarchical_semantic", "routing_path": routing_path,
            "query_embedded": True, "facts": facts_out, "passages": list(passages_out.values())}

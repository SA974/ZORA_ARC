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

TOP_DOMAINS = 2  # nombre de domaines retenus à la couche racine du routage descendant


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


def _route_top_domains(cur, lit: str, k: int) -> list[dict[str, Any]]:
    """Couche racine du routage : sélectionne les top-k domaines par sim(q, domaine)."""
    cur.execute(
        """
        select id, label, 1 - (embedding <=> %s::vector) as sim
        from hmem.memory_nodes
        where layer_id = %s and embedding is not null
        order by embedding <=> %s::vector
        limit %s
        """,
        (lit, _layer_id("domain"), lit, k),
    )
    return [{"id": str(r["id"]), "label": r["label"], "sim": round(float(r["sim"]), 4)} for r in cur.fetchall()]


def _facts_under_domains(cur, lit: str, domain_ids: list[str], limit: int) -> list[dict[str, Any]]:
    """Couche faits : ne score QUE les faits atteignables depuis les domaines retenus
    (élagage index-based) — `M^(fact) = ⋃_{d∈domaines} TopK_{f∈Child(d)} sim(q,f)`."""
    cur.execute(
        """
        select f.id, f.subject, f.predicate, f.object_value,
               1 - (f.embedding <=> %s::vector) as similarity,
               coalesce(vaf.salience_now, f.salience, 1.0) as salience
        from hmem.memory_nodes dn
        join hmem.memory_edges e on e.source_node_id = dn.id and e.edge_type = 'routes_to'
        join hmem.memory_nodes fn on fn.id = e.target_node_id and fn.layer_id = %s
        join memgraph.mem_facts f
          on fn.target_schema = 'memgraph' and fn.target_table = 'mem_facts' and fn.target_id = f.id
        left join memgraph.v_active_facts vaf on vaf.id = f.id
        where dn.id = any(%s) and f.embedding is not null
        order by f.embedding <=> %s::vector
        limit %s
        """,
        (lit, _layer_id("fact"), domain_ids, lit, limit),
    )
    return [dict(r) for r in cur.fetchall()]


def _facts_flat(cur, lit: str, limit: int) -> list[dict[str, Any]]:
    """Repli plat : score tous les faits de la couche `fact` (si aucun domaine n'a d'embedding)."""
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
        (lit, _layer_id("fact"), lit, limit),
    )
    return [dict(r) for r in cur.fetchall()]


def hmem_retrieve(query: str, limit: int = 8) -> dict[str, Any]:
    """Retrieval H-MEM par routage index-based descendant.

    domain (top-k par sim) -> faits SOUS ces domaines (élagage) -> passages-preuves.
    Repli plat si aucun domaine n'a encore d'embedding ; repli lexical si pas d'embedding requête.
    """
    routing_path = HMemRouter().route_query(query)
    qvec = EmbeddingService().try_embed_query(query)
    if qvec is None:
        facts = MemGraphService().get_facts_for_query(query, limit=limit)
        return {"mode": "lexical_fallback", "routing_path": routing_path,
                "query_embedded": False, "selected_domains": [], "facts": facts, "passages": []}

    lit = to_pgvector(qvec)
    with get_connection() as conn, conn.cursor() as cur:
        domains = _route_top_domains(cur, lit, TOP_DOMAINS)
        if domains:
            mode = "hierarchical_index_routing"
            rows = _facts_under_domains(cur, lit, [d["id"] for d in domains], limit)
        else:
            mode = "hierarchical_semantic_flat"  # hiérarchie pas encore dotée d'embeddings domaine
            rows = _facts_flat(cur, lit, limit)

        facts_out: list[dict[str, Any]] = []
        passages_out: dict[str, dict[str, Any]] = {}
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
    return {"mode": mode, "routing_path": routing_path, "query_embedded": True,
            "selected_domains": domains, "facts": facts_out, "passages": list(passages_out.values())}

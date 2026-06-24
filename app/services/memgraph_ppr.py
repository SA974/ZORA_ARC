"""Retrieval MemGraphRAG par Personalized PageRank conforme (arXiv:2606.00610).

Reproduit l'esprit du papier : un graphe faits/entités/passages, une personnalisation
initialisée par similarité à la requête —
  - entité : moyenne des Sim(q, f) de ses faits, atténuée par suppression de hub 1/log(deg+1)
    (empêche les entités trop génériques de dominer la propagation) ;
  - fait    : Sim(q, fait) ;
  - passage : moyenne des Sim(q, f) de ses faits-preuves ;
puis propagation `v^(k+1) = (1-λ)Wv^(k) + λv^(0)` avec λ=0.5 (= restart de networkx ; le
paramètre `alpha` de networkx vaut donc 1-λ = 0.5).
"""
from __future__ import annotations

import logging
import math
from typing import Any

from app.db import get_connection
from app.services.embedding_service import EmbeddingService, to_pgvector

logger = logging.getLogger(__name__)

LAMBDA_RESTART = 0.5  # poids de téléportation du papier ; networkx alpha = 1 - LAMBDA_RESTART


def entity_init(fact_sims: list[float], degree: int) -> float:
    """Init PPR d'une entité : moyenne des sim de ses faits × suppression de hub 1/log(deg+1)."""
    if not fact_sims:
        return 0.0
    mean_sim = sum(fact_sims) / len(fact_sims)
    return max(0.0, mean_sim) / math.log(degree + 1 + math.e)  # +e -> dénominateur >= 1


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in weights.values() if v > 0)
    if total <= 0:
        return {}
    return {k: v / total for k, v in weights.items() if v > 0}


def _personalized_pagerank(
    g, personalization: dict[str, float], lam: float, *, iters: int = 40, tol: float = 1e-6
) -> dict[str, float]:
    """Itération de puissance PPR pure-Python : `v^(k+1) = (1-λ)·W·v^(k) + λ·v^(0)`.

    Graphe non orienté pondéré (networkx) ; évite numpy/scipy. W = transition normalisée
    par les poids sortants. Les nœuds pendants redistribuent leur masse via la téléportation.
    """
    nodes = list(g.nodes)
    if not nodes:
        return {}
    v0 = {n: personalization.get(n, 0.0) for n in nodes}
    s = sum(v0.values()) or 1.0
    v0 = {n: x / s for n, x in v0.items()}
    v = dict(v0)
    wsum = {u: (sum(d.get("weight", 1.0) for d in g[u].values()) or 0.0) for u in nodes}
    for _ in range(iters):
        nxt = {n: lam * v0[n] for n in nodes}
        dangling = 0.0
        for u in nodes:
            if wsum[u] <= 0:
                dangling += (1 - lam) * v[u]
                continue
            share = (1 - lam) * v[u]
            for nb, d in g[u].items():
                nxt[nb] += share * (d.get("weight", 1.0) / wsum[u])
        if dangling:  # masse des nœuds pendants -> redistribuée selon v0
            for n in nodes:
                nxt[n] += dangling * v0[n]
        delta = sum(abs(nxt[n] - v[n]) for n in nodes)
        v = nxt
        if delta < tol:
            break
    return v


def ppr_retrieve(query: str, limit: int = 8, *, max_facts: int = 2000) -> dict[str, Any]:
    """Retrieval par PPR conforme. Retourne faits et passages classés par score PPR."""
    try:
        import networkx as nx
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "networkx absent", "facts": [], "passages": []}

    qvec = EmbeddingService().try_embed_query(query)
    if qvec is None:
        return {"ok": False, "error": "embedding requête indisponible", "facts": [], "passages": []}
    lit = to_pgvector(qvec)

    with get_connection() as conn, conn.cursor() as cur:
        # Faits + similarité à la requête (bornés aux plus pertinents pour la tractabilité)
        cur.execute(
            """
            select f.id, f.subject, f.predicate, f.object_value,
                   1 - (f.embedding <=> %s::vector) as sim,
                   coalesce(vaf.salience_now, f.salience, 1.0) as salience
            from memgraph.mem_facts f
            left join memgraph.v_active_facts vaf on vaf.id = f.id
            where f.embedding is not null
            order by f.embedding <=> %s::vector
            limit %s
            """,
            (lit, lit, max_facts),
        )
        facts = cur.fetchall()
        if not facts:
            return {"ok": True, "facts": [], "passages": [], "note": "aucun fait vectorisé"}

        fact_ids = [str(f["id"]) for f in facts]
        # Faits -> passages (preuves) via les bridges MemGraphRAG
        cur.execute(
            """
            select left_id::text as fact_id, right_id::text as passage_id
            from memgraph.mem_bridges
            where left_type='fact' and right_type='passage' and left_id = any(%s)
            """,
            (fact_ids,),
        )
        bridges = cur.fetchall()
        # Entités (nom + degré approx via correspondance texte dans les faits)
        cur.execute("select id, name from memgraph.mem_entities")
        entities = cur.fetchall()

    # --- Construction du graphe ---
    g = nx.Graph()
    sim_by_fact = {str(f["id"]): max(0.0, float(f["sim"])) for f in facts}
    fact_text = {str(f["id"]): f"{f['subject']} {f['object_value']}".lower() for f in facts}

    perso: dict[str, float] = {}
    for fid, sim in sim_by_fact.items():
        node = f"f:{fid}"
        g.add_node(node)
        perso[node] = sim  # init fait = Sim(q, fait)

    passage_facts: dict[str, list[str]] = {}
    for b in bridges:
        fnode, pnode = f"f:{b['fact_id']}", f"p:{b['passage_id']}"
        if fnode in g:
            g.add_edge(fnode, pnode, weight=1.0)
            passage_facts.setdefault(b["passage_id"], []).append(b["fact_id"])
    # init passage = moyenne des sim de ses faits-preuves
    for pid, fids in passage_facts.items():
        sims = [sim_by_fact.get(fid, 0.0) for fid in fids]
        perso[f"p:{pid}"] = sum(sims) / len(sims) if sims else 0.0

    # Entités : relier aux faits par correspondance de nom ; init avec suppression de hub
    for e in entities:
        ename = (e["name"] or "").lower().strip()
        if len(ename) < 3:
            continue
        matched = [fid for fid, txt in fact_text.items() if ename in txt]
        if not matched:
            continue
        enode = f"e:{e['id']}"
        for fid in matched:
            g.add_edge(enode, f"f:{fid}", weight=0.5)
        perso[enode] = entity_init([sim_by_fact[fid] for fid in matched], degree=len(matched))

    personalization = _normalize(perso)
    if not personalization:
        return {"ok": True, "facts": [], "passages": [], "note": "personnalisation vide"}

    scores = _personalized_pagerank(g, personalization, LAMBDA_RESTART)

    # --- Classement des faits et passages par score PPR ---
    fact_meta = {str(f["id"]): f for f in facts}
    ranked_facts = sorted(
        ((fid, scores.get(f"f:{fid}", 0.0)) for fid in fact_ids), key=lambda x: x[1], reverse=True
    )[:limit]
    facts_out = [{
        "id": fid, "subject": fact_meta[fid]["subject"], "predicate": fact_meta[fid]["predicate"],
        "object": fact_meta[fid]["object_value"], "ppr_score": round(score, 6),
        "similarity": round(sim_by_fact[fid], 4),
    } for fid, score in ranked_facts]

    ranked_passages = sorted(
        ((pid, scores.get(f"p:{pid}", 0.0)) for pid in passage_facts), key=lambda x: x[1], reverse=True
    )[:limit]
    passages_out = [{"id": pid, "ppr_score": round(score, 6)} for pid, score in ranked_passages if score > 0]

    return {"ok": True, "mode": "memgraphrag_ppr", "lambda": LAMBDA_RESTART,
            "facts": facts_out, "passages": passages_out}

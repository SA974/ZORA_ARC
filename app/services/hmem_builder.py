"""Peuplement de la mémoire hiérarchique H-MEM (hmem.memory_nodes / memory_edges).

Hiérarchie 4 niveaux (fidèle arXiv:2507.22925 — section/subsection/subsubsection/contenu) :

    domain ──routes_to──> theme ──routes_to──> subtheme ──routes_to──> fait ──evidences──> passage
                                                              │
                                                        routes_to──> entité

- `domain`   : domaine documentaire (agronomie, geographie_sante, …).
- `theme`    : catégorie sémantique dérivée du type d'entité dominant (person/org/place/concept/…).
- `subtheme` : prédicat normalisé — regroupement de faits du même type de relation.
- `fait`     : pointe vers memgraph.mem_facts.
- `entité`   : pointe vers memgraph.mem_entities.
- `passage`  : pointe vers memgraph.mem_passages (preuve textuelle).

Déduplication par sélection-puis-insertion (pas de contrainte unique sur memory_nodes).
Tout est fait dans UNE transaction par appel : cohérence ou rien.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from psycopg.types.json import Jsonb

from app.db import get_connection
from app.services.embedding_service import EmbeddingService, to_pgvector

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def _layer_id(name: str) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select id from hmem.memory_layers where name = %s", (name,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"couche H-MEM inconnue: {name!r}")
        return str(row["id"])


@lru_cache(maxsize=64)
def _domain_embedding(domain: str) -> str | None:
    """Embedding (littéral pgvector) du libellé de domaine, pour le routage index-based.
    Mis en cache par domaine ; None si l'embedder est indisponible (routage -> repli plat)."""
    vec = EmbeddingService().try_embed_query(domain)
    return to_pgvector(vec) if vec is not None else None


# Mapping entity_type → theme sémantique (fidèle au niveau "category" du papier H-MEM)
_ENTITY_TYPE_TO_THEME: dict[str, str] = {
    "person":  "acteurs",
    "org":     "organisations",
    "place":   "lieux_et_territoires",
    "concept": "concepts_et_notions",
    "product": "produits_et_technologies",
    "date":    "temporalite",
    "other":   "divers",
}

def _entity_type_to_theme(entity_type: str) -> str:
    """Mappe un entity_type MemGraphRAG vers un thème H-MEM."""
    return _ENTITY_TYPE_TO_THEME.get((entity_type or "other").lower(), "divers")

def _predicate_to_subtheme(predicate: str) -> str:
    """Normalise un prédicat en sous-thème (remplace les séparateurs, tronque à 40 car)."""
    sub = predicate.lower().replace(" ", "_").replace("-", "_")
    return sub[:40] if sub else "relation"


class HMemBuilder:
    def index_extraction(
        self,
        domain: str,
        passage_id: str,
        entity_ids: list[str],
        fact_ids: list[str],
        *,
        fact_predicates: dict[str, str] | None = None,
        entity_types: dict[str, str] | None = None,
    ) -> dict[str, int]:
        """Indexe une extraction dans H-MEM à 4 niveaux.

        Hiérarchie : domain → theme → subtheme → fait/entité → passage.
        fact_predicates : {fact_id: predicate} pour dériver les sous-thèmes.
        entity_types    : {entity_id: entity_type} pour dériver les thèmes.
        """
        created_nodes = 0
        created_edges = 0
        fp = fact_predicates or {}
        et = entity_types or {}
        dom_emb = _domain_embedding(domain)  # calculé hors transaction (appel réseau)

        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # Niveau 1 : domaine
                    dom_node, c = self._ensure_label_node(cur, "domain", domain, embedding=dom_emb)
                    created_nodes += c

                    # Passage (feuille preuve — optionnel pour le backfill)
                    pass_node = None
                    if passage_id:
                        pass_node, c = self._ensure_target_node(
                            cur, "passage", "memgraph", "mem_passages", passage_id, label="passage"
                        )
                        created_nodes += c

                    # Faits : domain → theme(prédicat) → subtheme(prédicat) → fait → passage
                    for fid in fact_ids:
                        predicate = fp.get(fid, "relation")
                        theme_lbl = _predicate_to_subtheme(predicate)   # theme = famille de prédicats
                        subtheme_lbl = theme_lbl                         # subtheme = prédicat exact ici

                        theme_node, c = self._ensure_label_node(cur, "theme", f"{domain}/{theme_lbl}")
                        created_nodes += c
                        created_edges += self._link(cur, dom_node, theme_node, "routes_to", 0.7)

                        sub_node, c = self._ensure_label_node(cur, "subtheme", f"{domain}/{theme_lbl}/{subtheme_lbl}")
                        created_nodes += c
                        created_edges += self._link(cur, theme_node, sub_node, "routes_to", 0.8)

                        fnode, c = self._ensure_target_node(
                            cur, "fact", "memgraph", "mem_facts", fid, label="fact"
                        )
                        created_nodes += c
                        created_edges += self._link(cur, sub_node, fnode, "routes_to", 0.9)
                        if pass_node:
                            created_edges += self._link(cur, fnode, pass_node, "evidences", 1.0)

                    # Entités : domain → theme(entity_type) → entité
                    for eid in entity_ids:
                        etype = et.get(eid, "other")
                        theme_lbl = _entity_type_to_theme(etype)
                        theme_node, c = self._ensure_label_node(cur, "theme", f"{domain}/{theme_lbl}")
                        created_nodes += c
                        created_edges += self._link(cur, dom_node, theme_node, "routes_to", 0.7)

                        enode, c = self._ensure_target_node(
                            cur, "entity", "memgraph", "mem_entities", eid, label="entity"
                        )
                        created_nodes += c
                        created_edges += self._link(cur, theme_node, enode, "routes_to", 0.6)

        return {"nodes": created_nodes, "edges": created_edges}

    # --- helpers ---------------------------------------------------------------

    def _ensure_label_node(self, cur, layer: str, label: str, *, embedding: str | None = None) -> tuple[str, int]:
        """Nœud sans cible (domaine/thème), dédupliqué par (layer, label).

        `embedding` (littéral pgvector) alimente le routage index-based ; backfillé si le
        nœud existait sans embedding.
        """
        lid = _layer_id(layer)
        cur.execute(
            "select id, embedding from hmem.memory_nodes where layer_id=%s and label=%s "
            "and target_id is null limit 1",
            (lid, label),
        )
        row = cur.fetchone()
        if row:
            if embedding is not None and row["embedding"] is None:
                cur.execute("update hmem.memory_nodes set embedding=%s::vector where id=%s",
                            (embedding, str(row["id"])))
            return str(row["id"]), 0
        cur.execute(
            "insert into hmem.memory_nodes(layer_id, label, metadata, embedding) "
            "values (%s, %s, %s::jsonb, %s::vector) returning id",
            (lid, label, Jsonb({"origin": "hmem_builder"}), embedding),
        )
        return str(cur.fetchone()["id"]), 1

    def _ensure_target_node(
        self, cur, layer: str, schema: str, table: str, target_id: str, *, label: str
    ) -> tuple[str, int]:
        """Nœud pointant vers une ligne (entité/fait/passage), dédupliqué par cible."""
        lid = _layer_id(layer)
        cur.execute(
            "select id from hmem.memory_nodes where target_schema=%s and target_table=%s "
            "and target_id=%s limit 1",
            (schema, table, target_id),
        )
        row = cur.fetchone()
        if row:
            return str(row["id"]), 0
        cur.execute(
            "insert into hmem.memory_nodes(layer_id, label, target_schema, target_table, target_id, metadata) "
            "values (%s, %s, %s, %s, %s, %s::jsonb) returning id",
            (lid, label, schema, table, target_id, Jsonb({"origin": "hmem_builder"})),
        )
        return str(cur.fetchone()["id"]), 1

    def _link(self, cur, source_id: str, target_id: str, edge_type: str, weight: float) -> int:
        """Arête dédupliquée par (source, target, type)."""
        cur.execute(
            "select 1 from hmem.memory_edges where source_node_id=%s and target_node_id=%s and edge_type=%s limit 1",
            (source_id, target_id, edge_type),
        )
        if cur.fetchone():
            return 0
        cur.execute(
            "insert into hmem.memory_edges(source_node_id, target_node_id, edge_type, weight) values (%s, %s, %s, %s)",
            (source_id, target_id, edge_type, weight),
        )
        return 1

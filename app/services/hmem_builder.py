"""Peuplement de la mémoire hiérarchique H-MEM (hmem.memory_nodes / memory_edges).

Construit, à partir d'une extraction MemGraphRAG, la hiérarchie navigable :

    domain ──routes_to──> entité ─┐
       │                          │
       └────routes_to──> fait ──evidences──> passage

- `domain`  : nœud racine par domaine documentaire (agronomie, geographie_sante, …).
- `entité`  : pointe vers memgraph.mem_entities.
- `fait`    : pointe vers memgraph.mem_facts.
- `passage` : pointe vers memgraph.mem_passages (preuve textuelle).

Déduplication par sélection-puis-insertion (pas de contrainte unique sur memory_nodes).
Tout est fait dans UNE transaction par appel : cohérence ou rien.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from psycopg.types.json import Jsonb

from app.db import get_connection

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def _layer_id(name: str) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select id from hmem.memory_layers where name = %s", (name,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"couche H-MEM inconnue: {name!r}")
        return str(row["id"])


class HMemBuilder:
    def index_extraction(
        self,
        domain: str,
        passage_id: str,
        entity_ids: list[str],
        fact_ids: list[str],
    ) -> dict[str, int]:
        """Indexe une extraction dans H-MEM. Retourne le nombre de nœuds/arêtes créés."""
        created_nodes = 0
        created_edges = 0
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    dom_node, c = self._ensure_label_node(cur, "domain", domain)
                    created_nodes += c
                    pass_node, c = self._ensure_target_node(
                        cur, "passage", "memgraph", "mem_passages", passage_id, label="passage"
                    )
                    created_nodes += c

                    for fid in fact_ids:
                        fnode, c = self._ensure_target_node(
                            cur, "fact", "memgraph", "mem_facts", fid, label="fact"
                        )
                        created_nodes += c
                        created_edges += self._link(cur, dom_node, fnode, "routes_to", 0.5)
                        created_edges += self._link(cur, fnode, pass_node, "evidences", 1.0)

                    for eid in entity_ids:
                        enode, c = self._ensure_target_node(
                            cur, "entity", "memgraph", "mem_entities", eid, label="entity"
                        )
                        created_nodes += c
                        created_edges += self._link(cur, dom_node, enode, "routes_to", 0.4)

        return {"nodes": created_nodes, "edges": created_edges}

    # --- helpers ---------------------------------------------------------------

    def _ensure_label_node(self, cur, layer: str, label: str) -> tuple[str, int]:
        """Nœud sans cible (domaine/thème), dédupliqué par (layer, label)."""
        lid = _layer_id(layer)
        cur.execute(
            "select id from hmem.memory_nodes where layer_id=%s and label=%s "
            "and target_id is null limit 1",
            (lid, label),
        )
        row = cur.fetchone()
        if row:
            return str(row["id"]), 0
        cur.execute(
            "insert into hmem.memory_nodes(layer_id, label, metadata) values (%s, %s, %s::jsonb) returning id",
            (lid, label, Jsonb({"origin": "hmem_builder"})),
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

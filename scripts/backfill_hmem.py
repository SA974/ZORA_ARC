"""Backfill H-MEM : peuple les nœuds H-MEM pour les faits/entités legacy (sans nœuds existants).

Pour chaque fait vectorisé sans nœud H-MEM, crée la hiérarchie complète :
  domain → theme(prédicat) → subtheme(prédicat) → fait → passage

Le domaine est dérivé du document source (metadata.domain, sinon 'bibliotheque').
Resumable : saute les faits déjà indexés. Progression affichée tous les BATCH_SIZE faits.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection
from app.services.hmem_builder import HMemBuilder

BATCH_SIZE = 50
DEFAULT_DOMAIN = "bibliotheque"


def get_legacy_facts() -> list[dict]:
    """Retourne les faits vectorisés sans nœuds H-MEM."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            select f.id, f.predicate, f.source_document_id,
                   d.metadata->>'domain' as domain
            from memgraph.mem_facts f
            left join zora.documents d on d.id = f.source_document_id
            where f.embedding is not null
              and not exists (
                select 1 from hmem.memory_nodes n
                where n.target_table = 'mem_facts' and n.target_id = f.id
              )
            order by f.created_at
        """)
        return [dict(r) for r in cur.fetchall()]


def get_passages_for_fact(fact_id: str) -> list[str]:
    """Retourne les passage_ids liés à un fait."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            select right_id::text as passage_id from memgraph.mem_bridges
            where left_type = 'fact' and left_id = %s::uuid and right_type = 'passage'
        """, (fact_id,))
        return [r["passage_id"] for r in cur.fetchall()]


def main() -> None:
    builder = HMemBuilder()
    facts = get_legacy_facts()
    total = len(facts)
    print(f"Faits legacy sans nœuds H-MEM : {total}")
    if total == 0:
        print("Rien à backfiller.")
        return

    nodes_created = 0
    edges_created = 0
    done = 0

    for fact in facts:
        fid = str(fact["id"])
        domain = fact.get("domain") or DEFAULT_DOMAIN
        predicate = fact.get("predicate") or "relation"
        passage_ids = get_passages_for_fact(fid)

        if not passage_ids:
            # Pas de passage lié : créer un nœud fait sans preuve (domain→theme→subtheme→fait seulement)
            try:
                r = builder.index_extraction(
                    domain=domain, passage_id=None,
                    entity_ids=[], fact_ids=[fid],
                    fact_predicates={fid: predicate},
                )
                nodes_created += r["nodes"]; edges_created += r["edges"]
            except Exception as exc:  # noqa: BLE001
                pass
        else:
            for pid in passage_ids:
                try:
                    r = builder.index_extraction(
                        domain=domain, passage_id=pid,
                        entity_ids=[], fact_ids=[fid],
                        fact_predicates={fid: predicate},
                    )
                    nodes_created += r["nodes"]; edges_created += r["edges"]
                except Exception as exc:  # noqa: BLE001
                    pass

        done += 1
        if done % BATCH_SIZE == 0 or done == total:
            pct = round(100 * done / total, 1)
            print(f"  [{done}/{total} {pct}%] noeuds={nodes_created} arêtes={edges_created}")

    print(f"\nBackfill H-MEM terminé : {done} faits, {nodes_created} nœuds, {edges_created} arêtes créés.")


if __name__ == "__main__":
    main()

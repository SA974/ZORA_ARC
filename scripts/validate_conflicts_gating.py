"""Validation e2e des items #3 et #4 : conflits multi-types + gating de schéma.

Crée directement des faits dans la DB pour tester :
  #3 Conflits détectés avec les bons types (mutuellement_exclusif, granularité)
  #4 Gating de schéma : schémas candidate→stable après FREQUENCY_THRESHOLD utilisations
"""
from __future__ import annotations

import sys
from pathlib import Path

# Console Windows UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection
from app.services.conflict_service import ConflictService
from app.services.schema_gating import SchemaGatingService
from app.services.temporal_service import TemporalService


def create_test_facts() -> list[str]:
    """Crée des faits de test avec conflits potentiels."""
    temporal = TemporalService()
    fact_ids = []

    # Faits mutuellement exclusifs : Alice is happy / Alice is not happy
    f1 = temporal.add_fact(
        subject="Alice", predicate="is", object_value="happy",
        provenance_text="Alice is happy in the morning.", source_document_id=None
    )
    fact_ids.append(str(f1["id"]))

    f2 = temporal.add_fact(
        subject="Alice", predicate="is", object_value="not happy",
        provenance_text="Alice is not happy in the evening.", source_document_id=None
    )
    fact_ids.append(str(f2["id"]))

    # Faits de granularité : Bob lives in Paris / Bob lives in France
    f3 = temporal.add_fact(
        subject="Bob", predicate="lives_in", object_value="Paris",
        provenance_text="Bob lives in Paris, a beautiful city.", source_document_id=None
    )
    fact_ids.append(str(f3["id"]))

    f4 = temporal.add_fact(
        subject="Bob", predicate="lives_in", object_value="France",
        provenance_text="Bob lives in France.", source_document_id=None
    )
    fact_ids.append(str(f4["id"]))

    # Faits pour tester gating (même prédicat x3 -> stable au 3ème)
    for i in range(3):
        f = temporal.add_fact(
            subject=f"Charlie{i}", predicate="has_pet", object_value=f"pet{i}",
            provenance_text=f"Charlie{i} has a pet.", source_document_id=None
        )
        fact_ids.append(str(f["id"]))

    return fact_ids


def cleanup(fact_ids: list[str]) -> None:
    """Supprime les faits de test."""
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("delete from memgraph.mem_conflicts where fact_id = any(%s)", (fact_ids,))
                cur.execute("delete from memgraph.mem_facts where id = any(%s)", (fact_ids,))


def main() -> int:
    temporal = TemporalService()
    conflict_svc = ConflictService()
    schema_svc = SchemaGatingService()

    print("Création de faits de test...")
    fact_ids = create_test_facts()
    print(f"  {len(fact_ids)} faits créés")

    print("\n=== #3 DÉTECTION DE CONFLITS ===")
    # Détecte les conflits du 2ème fait (mutuellement exclusif avec le 1er)
    conflicts_f2 = conflict_svc.detect_conflicts(fact_ids[1])
    print(f"Conflits pour Alice fact (not happy):")
    for c in conflicts_f2.get("conflicts", []):
        print(f"  type={c['conflict_type']}, evidence={c['evidence_comparison'][:60]}...")

    # Détecte les conflits du 4ème fait (granularité avec le 3ème)
    conflicts_f4 = conflict_svc.detect_conflicts(fact_ids[3])
    print(f"Conflits pour Bob fact (France):")
    for c in conflicts_f4.get("conflicts", []):
        print(f"  type={c['conflict_type']}, evidence={c['evidence_comparison'][:60]}...")

    print("\n=== #4 GATING DE SCHEMA ===")
    # Simuler l'enregistrement du schéma via le pipeline (register_schema_usage x 3)
    print("Enregistrement du schéma 'has_pet' (3 usages -> stable):")
    for i in range(3):
        info = schema_svc.register_schema_usage("has_pet")
        print(f"  usage {i+1}: {info}")

    schema_info = schema_svc.get_schema_info("has_pet")
    if schema_info:
        print(f"Schéma 'has_pet': status={schema_info['status']} freq={schema_info['frequency']}/{schema_info['threshold']}")
    else:
        print("Schéma 'has_pet' introuvable")

    # Vérifier que les autres schémas sont en candidate
    for pred in ["is", "lives_in"]:
        info = schema_svc.get_schema_info(pred)
        if info:
            print(f"  {pred}: status={info['status']} freq={info['frequency']}")

    print("\nNettoyage...")
    cleanup(fact_ids)

    # Checks
    has_mut_excl = any(c["conflict_type"] == "mutually_exclusive" for c in conflicts_f2.get("conflicts", []))
    has_temporal = any(c["conflict_type"] == "temporal" for c in conflicts_f4.get("conflicts", []))
    has_gating = schema_info and schema_info.get("status") == "stable"

    print("\n=== VALIDATION ===")
    checks = [
        ("#3 conflit mutuellement_exclusif détecté", has_mut_excl),
        ("#3 conflit temporel détecté (granularité via sim)", has_temporal),
        ("#4 schéma stable après 3 usages", has_gating),
    ]
    for name, c in checks:
        print(f"  [{'PASS' if c else 'FAIL'}] {name}")

    npass = sum(1 for _, c in checks if c)
    print(f"\n{npass}/{len(checks)} PASS")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

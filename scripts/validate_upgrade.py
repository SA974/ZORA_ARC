"""Validation e2e de la mise à niveau papiers : routage index-based H-MEM (#1) + PPR conforme (#2).

Ingère 2 PDF dans 2 domaines distincts (avec extraction), puis vérifie :
  #1 hmem_retrieve fait du routage index-based (mode + domaine sélectionné cohérent) ;
  #2 ppr_retrieve renvoie des faits classés par PageRank personnalisé.
Nettoie ensuite les documents de test (faits/passages/nœuds H-MEM fait+passage).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Console Windows en cp1252 : forcer UTF-8 pour les caractères comme λ (cf. gotcha Hermes).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz

from app.db import get_connection
from app.services.document_ingestion import ingest_pdf_file
from app.services.hmem_retrieval import hmem_retrieve
from app.services.memgraph_ppr import ppr_retrieve

DOCS = [
    ("agronomie", "Le theier Camellia sinensis pousse en altitude a La Reunion. "
                  "La theiculture beneficie du sol volcanique et de l'agroforesterie tropicale."),
    ("geomatique", "PostGIS gere les donnees spatiales. La teledetection cartographie les territoires "
                   "et l'hydrologie modelise les bassins versants par SIG."),
]


def make_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def cleanup(doc_ids: list[str]) -> None:
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for doc_id in doc_ids:
                    cur.execute(
                        "delete from hmem.memory_nodes where "
                        "(target_table='mem_facts' and target_id in (select id from memgraph.mem_facts where source_document_id=%s)) "
                        "or (target_table='mem_passages' and target_id in (select id from memgraph.mem_passages where source_document_id=%s))",
                        (doc_id, doc_id))
                    cur.execute("delete from memgraph.mem_facts where source_document_id=%s", (doc_id,))
                    cur.execute("delete from memgraph.mem_passages where source_document_id=%s", (doc_id,))
                    cur.execute("delete from zora.documents where id=%s", (doc_id,))


def main() -> int:
    doc_ids = []
    with tempfile.TemporaryDirectory() as d:
        for i, (domain, text) in enumerate(DOCS):
            pdf = Path(d) / f"doc{i}.pdf"
            make_pdf(pdf, text)
            res = ingest_pdf_file(pdf, domain, extract=True)
            doc_ids.append(res.get("document_id"))
            print(f"  ingéré [{domain}] -> {res.get('memgraph')}")

    # #1 — routage index-based : requête thé -> doit router vers 'agronomie'
    r1 = hmem_retrieve("culture du the en altitude a La Reunion", limit=5)
    print(f"\n#1 hmem_retrieve: mode={r1['mode']} domaines={[d.get('label') for d in r1.get('selected_domains', [])]}")
    if r1["facts"]:
        print("   top fait:", {k: r1["facts"][0][k] for k in ("subject", "predicate", "object", "score")})

    # #2 — PPR conforme
    r2 = ppr_retrieve("the agroforesterie La Reunion", limit=5)
    print(f"#2 ppr_retrieve: ok={r2.get('ok')} mode={r2.get('mode')} lambda={r2.get('lambda')} facts={len(r2.get('facts', []))}")
    if r2.get("facts"):
        print("   top fait PPR:", {k: r2["facts"][0][k] for k in ("subject", "object", "ppr_score")})

    domains_sel = [d.get("label") for d in r1.get("selected_domains", [])]
    checks = [
        ("#1 routage index-based actif", r1["mode"] == "hierarchical_index_routing"),
        ("#1 domaine(s) sélectionné(s)", len(domains_sel) > 0),
        ("#1 'agronomie' routé pour requête thé", "agronomie" in domains_sel),
        ("#1 faits renvoyés", len(r1["facts"]) > 0),
        ("#2 PPR conforme OK (λ=0.5)", r2.get("ok") and r2.get("lambda") == 0.5),
        ("#2 faits classés par PPR", len(r2.get("facts", [])) > 0 and "ppr_score" in (r2.get("facts") or [{}])[0]),
    ]

    cleanup(doc_ids)
    print("\nNettoyage : documents de test supprimés (domaines conservés).")

    print("\n=== VALIDATION MISE À NIVEAU ===")
    for name, c in checks:
        print(f"  [{'PASS' if c else 'FAIL'}] {name}")
    npass = sum(1 for _, c in checks if c)
    print(f"\n{npass}/{len(checks)} PASS")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

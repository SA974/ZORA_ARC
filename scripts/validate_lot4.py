"""Validation end-to-end Lot 4 : ingestion PDF + extraction MemGraphRAG, puis nettoyage.

Crée un PDF synthétique, l'ingère avec extract=True (LLM réel qwen:14b), vérifie que des
passages/faits sont créés et liés au document, puis SUPPRIME le document de test et ses
faits/passages/bridges (les entités déduplifiées sont laissées : partagées et inoffensives).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz

from app.db import get_connection
from app.services.document_ingestion import ingest_pdf_file

TEXT = (
    "Le theier, Camellia sinensis, pousse en altitude a La Reunion. "
    "L'agroforesterie associe arbres et cultures. "
    "PostgreSQL stocke les embeddings vectoriels via pgvector."
)


def make_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), TEXT)
    doc.save(str(path))
    doc.close()


def cleanup(doc_id: str) -> None:
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "delete from memgraph.mem_bridges where right_type='passage' and right_id in "
                    "(select id from memgraph.mem_passages where source_document_id=%s)", (doc_id,))
                cur.execute("delete from memgraph.mem_facts where source_document_id=%s", (doc_id,))
                cur.execute("delete from memgraph.mem_passages where source_document_id=%s", (doc_id,))
                cur.execute("delete from zora.documents where id=%s", (doc_id,))  # cascade chunks


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "test_lot4.pdf"
        make_pdf(pdf)
        res = ingest_pdf_file(pdf, "validation", extract=True)

    print("Résultat ingestion:", {k: res.get(k) for k in ("status", "chunks", "embeddings")})
    print("MemGraphRAG       :", res.get("memgraph"))
    doc_id = res.get("document_id")
    ok = bool(res.get("ok")) and res.get("status") == "ingested"

    mg = res.get("memgraph") or {}
    has_extraction = mg.get("status") == "done" and (mg.get("facts", 0) + mg.get("entities", 0)) > 0

    # Vérif en base : passages/faits liés au document
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select count(*) c from memgraph.mem_passages where source_document_id=%s", (doc_id,))
        n_pass = cur.fetchone()["c"]
        cur.execute("select count(*) c from memgraph.mem_facts where source_document_id=%s", (doc_id,))
        n_facts = cur.fetchone()["c"]
    print(f"En base : passages={n_pass} facts={n_facts}")

    if doc_id:
        cleanup(doc_id)
        print("Nettoyage : document de test + faits/passages supprimés.")

    print("\n=== VALIDATION LOT 4 ===")
    checks = [
        ("Ingestion PDF OK", ok),
        ("Extraction MemGraphRAG exécutée", has_extraction),
        ("Passages liés au document créés", n_pass > 0),
    ]
    for name, c in checks:
        print(f"  [{'PASS' if c else 'FAIL'}] {name}")
    npass = sum(1 for _, c in checks if c)
    print(f"\n{npass}/{len(checks)} PASS")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

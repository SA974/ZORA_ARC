"""Validation end-to-end Lot 4b : ingestion PDF -> H-MEM hiérarchique -> retrieval, puis nettoyage.

Ingère un PDF synthétique avec extract=True (construit aussi H-MEM), vérifie que des nœuds
H-MEM (domain/fact/passage) et arêtes sont créés, exécute hmem_retrieve, puis nettoie TOUT
(faits, passages, nœuds/arêtes H-MEM ciblant ce document, et le document).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz

from app.db import get_connection
from app.services.document_ingestion import ingest_pdf_file
from app.services.hmem_retrieval import hmem_retrieve

TEXT = (
    "Le theier Camellia sinensis pousse en altitude a La Reunion. "
    "L'agroforesterie associe des arbres et des cultures vivrieres. "
    "Le sol volcanique de La Reunion favorise la theiculture."
)


def make_pdf(path: Path) -> None:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), TEXT)
    doc.save(str(path))
    doc.close()


def hmem_counts(cur, doc_id: str) -> tuple[int, int]:
    """(nœuds fait/passage liés au doc, arêtes incidentes)."""
    cur.execute(
        """
        select n.id from hmem.memory_nodes n
        where (n.target_table='mem_facts' and n.target_id in
                 (select id from memgraph.mem_facts where source_document_id=%s))
           or (n.target_table='mem_passages' and n.target_id in
                 (select id from memgraph.mem_passages where source_document_id=%s))
        """,
        (doc_id, doc_id),
    )
    node_ids = [str(r["id"]) for r in cur.fetchall()]
    if not node_ids:
        return 0, 0
    cur.execute(
        "select count(*) c from hmem.memory_edges where source_node_id = any(%s) or target_node_id = any(%s)",
        (node_ids, node_ids),
    )
    return len(node_ids), cur.fetchone()["c"]


def cleanup(doc_id: str) -> None:
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # nœuds H-MEM ciblant faits/passages du doc -> arêtes cascade (FK on delete cascade)
                cur.execute(
                    """
                    delete from hmem.memory_nodes
                    where (target_table='mem_facts' and target_id in
                             (select id from memgraph.mem_facts where source_document_id=%s))
                       or (target_table='mem_passages' and target_id in
                             (select id from memgraph.mem_passages where source_document_id=%s))
                    """,
                    (doc_id, doc_id),
                )
                cur.execute("delete from memgraph.mem_facts where source_document_id=%s", (doc_id,))
                cur.execute("delete from memgraph.mem_passages where source_document_id=%s", (doc_id,))
                cur.execute("delete from zora.documents where id=%s", (doc_id,))


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "lot4b.pdf"
        make_pdf(pdf)
        res = ingest_pdf_file(pdf, "agronomie", extract=True)

    doc_id = res.get("document_id")
    mg = res.get("memgraph") or {}
    print("Ingestion :", {k: res.get(k) for k in ("status", "chunks")}, "| MemGraphRAG:", mg)

    with get_connection() as conn, conn.cursor() as cur:
        n_nodes, n_edges = hmem_counts(cur, doc_id)
    print(f"H-MEM : nodes(fait/passage)={n_nodes} edges={n_edges}")

    retr = hmem_retrieve("culture du the a La Reunion", limit=5)
    print(f"Retrieval : mode={retr['mode']} facts={len(retr['facts'])} passages={len(retr['passages'])}")
    if retr["facts"]:
        print("  top fait:", retr["facts"][0])

    if doc_id:
        cleanup(doc_id)
        print("Nettoyage : doc + faits + passages + nœuds H-MEM supprimés.")

    checks = [
        ("Ingestion + extraction OK", res.get("status") == "ingested" and mg.get("status") == "done"),
        ("H-MEM peuplé (nœuds + arêtes)", n_nodes > 0 and n_edges > 0),
        ("Retrieval H-MEM renvoie des faits scorés", retr["query_embedded"] and len(retr["facts"]) > 0),
        ("Faits scorés bornés [0,1]", all(0.0 <= f["score"] <= 1.0 for f in retr["facts"])),
    ]
    print("\n=== VALIDATION LOT 4b ===")
    for name, c in checks:
        print(f"  [{'PASS' if c else 'FAIL'}] {name}")
    npass = sum(1 for _, c in checks if c)
    print(f"\n{npass}/{len(checks)} PASS")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

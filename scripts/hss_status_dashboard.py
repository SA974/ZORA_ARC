"""Dashboard de statut ingestion HSS — affiche l'historique et l'état actuel."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection


def main() -> None:
    status_file = Path(__file__).resolve().parents[1] / "logs" / "hss_ingest_status.json"
    if not status_file.exists():
        print("Aucun statut d'ingestion trouvé (hss_ingest_status.json).")
        return

    with open(status_file, encoding="utf-8") as f:
        status = json.load(f)

    print("\n=== TABLEAU DE BORD INGESTION HSS ===")
    print(f"Dernière exécution : {status['timestamp']}")
    print(f"Résumé : {status['total_pdfs']} PDFs")
    print(f"  ✓ {status['processed']} succès")
    print(f"  ⊘ {status['skipped']} ignorés (déjà traités)")
    print(f"  ✗ {status['errors']} erreurs")

    if status["errors"] > 0:
        print("\nDétails des erreurs :")
        for r in status["results"]:
            if r["status"] == "error":
                print(f"  • {r['file']}: {r.get('error', 'erreur inconnue')}")

    print("\n=== STATISTIQUES DE BASE DE DONNÉES ===")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select count(*) c from zora.documents where metadata->>'source' = 'hss_folder'")
        total_docs = cur.fetchone()["c"]
        cur.execute("""
            select count(*) c from zora.chunks z
            where exists (select 1 from zora.documents d where d.id = z.document_id
                         and d.metadata->>'source' = 'hss_folder')
        """)
        total_chunks = cur.fetchone()["c"]
        cur.execute("""
            select count(*) c from memgraph.mem_facts f
            where exists (select 1 from zora.documents d where d.id = f.source_document_id
                         and d.metadata->>'source' = 'hss_folder')
        """)
        total_facts = cur.fetchone()["c"]
        cur.execute("""
            select count(*) c from hmem.memory_nodes n
            join zora.documents d on true
            where d.metadata->>'source' = 'hss_folder'
              and n.target_id::text in (select f.id::text from memgraph.mem_facts f where f.source_document_id = d.id)
        """)
        total_hmem = cur.fetchone()["c"]

    print(f"Documents HSS : {total_docs}")
    print(f"Chunks : {total_chunks}")
    print(f"Faits extraits : {total_facts}")
    print(f"Nœuds H-MEM : {total_hmem}")

    print("\n=== PROCHAINES EXÉCUTIONS ===")
    print("La tâche planifiée 'ARC-MEM HSS Watchdog' s'exécute :")
    print("  • Au démarrage du système")
    print("  • Toutes les 2 heures")
    print("\nLogs : C:\\Users\\Stephane_Arnoux\\arc-mem-bridge\\logs\\hss_ingest.log")


if __name__ == "__main__":
    main()

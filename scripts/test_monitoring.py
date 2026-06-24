"""Test le service de monitoring."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.monitoring_service import MonitoringService

def main():
    svc = MonitoringService()

    # Enregistrer des jobs de test
    job1_id = svc.register_job("ingest_hss_folder", "Ingestion du dossier HSS", "scripts/ingest_hss_folder.py")
    job2_id = svc.register_job("backfill_hmem", "Backfill H-MEM", "scripts/backfill_hmem.py")

    # Simuler exécution job 1
    svc.job_start(job1_id)
    svc.log_event(job1_id, "info", "Scan du dossier HSS")
    svc.job_complete(job1_id, items_processed=12, items_failed=0)

    # Simuler erreur job 2
    svc.job_start(job2_id)
    svc.log_event(job2_id, "info", "Traitement passage 42...")
    svc.job_error(job2_id, "Timeout sur passage 42 après 30s")

    # Stats d'ingestion
    svc.update_ingestion_stats(
        domain="global",
        files_detected=100,
        files_ingested=42,
        files_failed=1,
        chunks_created=5282,
        facts_extracted=25,
        db_records=18500,
    )

    # Afficher snapshot
    snapshot = svc.get_dashboard_snapshot()
    print("=== TEST MONITORING ===")
    print(f"Jobs: {snapshot['jobs']['total']} enregistres")
    print(f"  - En cours: {snapshot['jobs']['running']}")
    print(f"  - En erreur: {snapshot['jobs']['error']}")
    print(f"  - Succes: {snapshot['jobs']['success']}")
    print(f"Evenements: {len(snapshot['events'])} recents")
    print(f"Ingestion:")
    print(f"  - Total: {snapshot['ingestion']['total_files']}")
    print(f"  - Ingeres: {snapshot['ingestion']['ingested']}")
    print(f"  - Restants: {snapshot['ingestion']['remaining']}")
    print(f"  - Echoues: {snapshot['ingestion']['failed']}")
    print(f"  - Progression: {snapshot['ingestion']['progress_pct']}%")
    print(f"  - Chunks: {snapshot['ingestion']['chunks_created']}")
    print(f"  - Faits: {snapshot['ingestion']['facts_extracted']}")
    print("\n=== TEST OK ===")

if __name__ == "__main__":
    main()

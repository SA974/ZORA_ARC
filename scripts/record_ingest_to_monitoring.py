"""Enregistre l'ingestion HSS dans le monitoring."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.monitoring_service import MonitoringService

def main():
    svc = MonitoringService()

    # Enregistrer le job HSS
    job_id = svc.register_job(
        "ingest_hss_folder",
        "Ingestion du dossier HSS (Homo Sapiens Sapiens)",
        "scripts/ingest_hss_folder.py",
    )

    # Simuler l'exécution
    svc.job_start(job_id)
    svc.log_event(job_id, "info", "Scan du dossier F:\\Dropbox\\...\\HSS")
    svc.log_event(job_id, "started", "Ingestion batch: 12 PDFs trouvés")
    svc.job_complete(job_id, items_processed=12, items_failed=0)

    # Mettre à jour les stats globales
    svc.update_ingestion_stats(
        domain="global",
        files_detected=12,
        files_ingested=12,
        files_failed=0,
        chunks_created=5282,
        facts_extracted=0,  # Pas d'extraction LLM sur les PDFs bruts
        db_records=6294,
    )

    # Afficher le snapshot
    snapshot = svc.get_dashboard_snapshot()
    print("=== DASHBOARD SNAPSHOT ===")
    print(f"Timestamp: {snapshot['timestamp']}")
    print(
        f"Jobs: {snapshot['jobs']['total']} total ({snapshot['jobs']['success']} succes, {snapshot['jobs']['error']} erreurs)"
    )
    print(
        f"Ingestion: {snapshot['ingestion']['ingested']}/{snapshot['ingestion']['total_files']} ({snapshot['ingestion']['progress_pct']}%)"
    )
    print(f"Chunks: {snapshot['ingestion']['chunks_created']}")
    print(f"Faits: {snapshot['ingestion']['facts_extracted']}")
    print(f"Enregistrements DB: {snapshot['ingestion']['db_records']}")
    print(f"Evenements: {len(snapshot['events'])} recents")

if __name__ == "__main__":
    main()

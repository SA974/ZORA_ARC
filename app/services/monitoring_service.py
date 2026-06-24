"""Service de monitoring/supervision du dashboard.

Gère les jobs, événements et compteurs d'ingestion.
Interface entre les scripts d'ingestion et le dashboard.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.db import get_connection

logger = logging.getLogger(__name__)


class MonitoringService:
    """Supervision centralisée des jobs, événements et ingestion."""

    # Job status
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"

    # Event types
    STARTED = "started"
    COMPLETED = "completed"
    ERROR_EVENT = "error"
    SKIPPED = "skipped"
    INFO = "info"
    SUCCESS = "success"

    def register_job(self, name: str, description: str = "", script_path: str = "") -> str:
        """Enregistre un job (script). Retourne le job_id."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.monitoring_jobs(name, description, script_path, status)
                values (%s, %s, %s, %s)
                on conflict(name) do update set updated_at = now()
                returning id::text
                """,
                (name, description, script_path, self.IDLE),
            )
            return cur.fetchone()["id"]

    def job_start(self, job_id: str | UUID) -> None:
        """Marque un job comme démarré."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "update public.monitoring_jobs set status = %s, last_started_at = now(), updated_at = now() "
                "where id = %s",
                (self.RUNNING, str(job_id)),
            )
            conn.commit()
            self.log_event(job_id, self.STARTED, "Job démarré")

    def job_complete(self, job_id: str | UUID, items_processed: int = 0, items_failed: int = 0) -> None:
        """Marque un job comme complété avec succès."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.monitoring_jobs
                set status = %s, last_completed_at = now(),
                    last_duration_seconds = extract(epoch from (now() - last_started_at)),
                    items_processed = %s, items_failed = %s,
                    last_error = null, updated_at = now()
                where id = %s
                """,
                (self.SUCCESS, items_processed, items_failed, str(job_id)),
            )
            conn.commit()
            self.log_event(
                job_id, self.COMPLETED,
                f"Job complété: {items_processed} traités, {items_failed} erreurs"
            )

    def job_error(self, job_id: str | UUID, error: str) -> None:
        """Marque un job comme échoué."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.monitoring_jobs
                set status = %s, last_completed_at = now(),
                    last_duration_seconds = extract(epoch from (now() - last_started_at)),
                    last_error = %s, updated_at = now()
                where id = %s
                """,
                (self.ERROR, error[:500], str(job_id)),
            )
            conn.commit()
            self.log_event(job_id, self.ERROR_EVENT, f"Job en erreur: {error[:200]}")

    def log_event(self, job_id: str | UUID | None, event_type: str, message: str, details: dict[str, Any] | None = None) -> None:
        """Enregistre un événement."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.monitoring_events(job_id, event_type, message, details)
                values (%s, %s, %s, %s::jsonb)
                """,
                (str(job_id) if job_id else None, event_type, message, details),
            )
            conn.commit()

    def update_ingestion_stats(
        self, domain: str = "global",
        files_detected: int | None = None, files_validated: int | None = None,
        files_ingested: int | None = None, files_failed: int | None = None,
        chunks_created: int | None = None, embeddings_generated: int | None = None,
        facts_extracted: int | None = None, db_records: int | None = None,
    ) -> None:
        """Met à jour les compteurs d'ingestion."""
        with get_connection() as conn, conn.cursor() as cur:
            # Récupérer ou créer l'enregistrement
            cur.execute(
                "insert into public.monitoring_ingestion_stats(domain) values (%s) "
                "on conflict(domain) do nothing",
                (domain,),
            )
            # Mettre à jour sélectivement
            updates = []
            params = []
            if files_detected is not None:
                updates.append("total_files_detected = %s")
                params.append(files_detected)
            if files_validated is not None:
                updates.append("total_files_validated = %s")
                params.append(files_validated)
            if files_ingested is not None:
                updates.append("total_files_ingested = %s")
                params.append(files_ingested)
            if files_failed is not None:
                updates.append("total_files_failed = %s")
                params.append(files_failed)
            if chunks_created is not None:
                updates.append("total_chunks_created = %s")
                params.append(chunks_created)
            if embeddings_generated is not None:
                updates.append("total_embeddings_generated = %s")
                params.append(embeddings_generated)
            if facts_extracted is not None:
                updates.append("total_facts_extracted = %s")
                params.append(facts_extracted)
            if db_records is not None:
                updates.append("total_db_records_stored = %s")
                params.append(db_records)

            if updates:
                updates.append("updated_at = now()")
                params.append(domain)
                sql = f"update public.monitoring_ingestion_stats set {', '.join(updates)} where domain = %s"
                cur.execute(sql, params)
            conn.commit()

    def get_jobs_summary(self) -> list[dict[str, Any]]:
        """Retourne le résumé des jobs."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("select * from public.v_monitoring_jobs_summary limit 50")
            return [dict(r) for r in cur.fetchall()]

    def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retourne les événements récents."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(f"select * from public.v_monitoring_recent_events limit {limit}")
            return [dict(r) for r in cur.fetchall()]

    def get_ingestion_stats(self, domain: str = "global") -> dict[str, Any]:
        """Retourne les compteurs d'ingestion."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("select * from public.monitoring_ingestion_stats where domain = %s", (domain,))
            row = cur.fetchone()
            if not row:
                return {
                    "domain": domain,
                    "total_files_detected": 0,
                    "total_files_ingested": 0,
                    "total_files_failed": 0,
                    "total_chunks_created": 0,
                    "total_facts_extracted": 0,
                }
            return dict(row)

    def get_dashboard_snapshot(self) -> dict[str, Any]:
        """Snapshot complet pour le dashboard (une requête)."""
        with get_connection() as conn, conn.cursor() as cur:
            # Jobs summary
            cur.execute("select * from public.v_monitoring_jobs_summary limit 20")
            jobs = [dict(r) for r in cur.fetchall()]

            # Events
            cur.execute("select * from public.v_monitoring_recent_events limit 20")
            events = [dict(r) for r in cur.fetchall()]

            # Stats ingestion
            cur.execute("select * from public.monitoring_ingestion_stats where domain = 'global'")
            stats = dict(cur.fetchone() or {})

            # Comptages
            cur.execute("select count(*) c from public.monitoring_jobs where status = 'running'")
            running_jobs = cur.fetchone()["c"]
            cur.execute("select count(*) c from public.monitoring_jobs where status = 'error'")
            error_jobs = cur.fetchone()["c"]
            cur.execute("select count(*) c from public.monitoring_jobs where status = 'success'")
            success_jobs = cur.fetchone()["c"]

        total_files = stats.get("total_files_detected", 0) or 0
        ingested = stats.get("total_files_ingested", 0) or 0
        remaining = max(0, total_files - ingested)
        failed = stats.get("total_files_failed", 0) or 0

        progress_pct = round(100 * ingested / total_files, 1) if total_files > 0 else 0

        return {
            "timestamp": datetime.now().isoformat(),
            "jobs": {
                "running": running_jobs,
                "error": error_jobs,
                "success": success_jobs,
                "total": len(jobs),
                "list": jobs,
            },
            "ingestion": {
                "total_files": total_files,
                "ingested": ingested,
                "remaining": remaining,
                "failed": failed,
                "progress_pct": progress_pct,
                "chunks_created": stats.get("total_chunks_created", 0),
                "facts_extracted": stats.get("total_facts_extracted", 0),
                "db_records": stats.get("total_db_records_stored", 0),
            },
            "events": events[:20],
        }

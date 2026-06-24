"""Ingestion batch des PDFs du dossier HSS (Homo Sapiens Sapiens) dans arc-mem-bridge.

Monitore : F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HSS
Peuple arc-mem-bridge via document_ingestion.ingest_pdf_file avec extraction multi-agents.
Statut écrit en JSON (logs/hss_ingest_status.json) pour la tâche planifiée Windows.

Resumable : saute les fichiers déjà traités (via hash SHA256 en metadata.pdf_sha256).
"""
from __future__ import annotations

import hashlib
import json
import logging
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
from app.services.document_ingestion import ingest_pdf_file

HSS_PATH = Path(r"F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HSS")
STATUS_FILE = Path(__file__).resolve().parents[1] / "logs" / "hss_ingest_status.json"
LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "hss_ingest.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def pdf_sha256(path: Path) -> str:
    """Calcule le SHA256 d'un PDF."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_processed_pdfs() -> dict[str, str]:
    """Retourne {pdf_title: sha256} des PDFs déjà ingérés depuis HSS."""
    processed = {}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            select d.title, d.metadata->>'pdf_sha256' as sha256
            from zora.documents d
            where d.metadata->>'source' = 'hss_folder'
              and d.metadata->>'pdf_sha256' is not null
        """)
        for r in cur.fetchall():
            if r["title"] and r["sha256"]:
                processed[r["title"]] = r["sha256"]
    return processed


def ingest_hss_batch() -> dict[str, any]:
    """Ingère tous les PDFs du dossier HSS non encore traités."""
    if not HSS_PATH.exists():
        logger.error(f"HSS path introuvable: {HSS_PATH}")
        return {"ok": False, "error": f"path not found: {HSS_PATH}", "results": []}

    LOG_FILE.parent.mkdir(exist_ok=True)
    processed = get_processed_pdfs()
    pdfs = sorted(HSS_PATH.glob("*.pdf"))
    logger.info(f"Dossier HSS: {len(pdfs)} PDFs trouvés, {len(processed)} déjà ingérés")

    results = []
    for pdf_path in pdfs:
        sha = pdf_sha256(pdf_path)
        # Utiliser le nom du fichier (sans .pdf) comme clé
        pdf_key = pdf_path.stem
        if pdf_key in processed and processed[pdf_key] == sha:
            logger.info(f"SKIP {pdf_path.name} (déjà ingéré)")
            results.append({"file": pdf_path.name, "status": "skipped", "reason": "already_processed"})
            continue

        logger.info(f"INGEST {pdf_path.name} (sha={sha[:8]}...)")
        try:
            res = ingest_pdf_file(
                pdf_path,
                domain="hss_homo_sapiens_sapiens",
                extract=True,
                detect_conflicts=True,
            )
            doc_id = res.get("document_id")
            # Mettre à jour le SHA256 et source en metadata
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "update zora.documents set metadata = jsonb_set("
                    "  jsonb_set(metadata, '{pdf_sha256}', %s), "
                    "  '{source}', '\"hss_folder\"') where id = %s",
                    (json.dumps(sha), doc_id),
                )
                conn.commit()
            logger.info(f"  ✓ {pdf_path.name} -> doc_id={doc_id}, "
                       f"faits={res.get('memgraph', {}).get('facts', 0)}")
            results.append({
                "file": pdf_path.name,
                "status": "success",
                "doc_id": doc_id,
                "memgraph": res.get("memgraph"),
            })
        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ {pdf_path.name}: {type(exc).__name__}: {exc}")
            results.append({
                "file": pdf_path.name,
                "status": "error",
                "error": f"{type(exc).__name__}: {str(exc)[:100]}",
            })

    # Écrire le statut JSON (pour la tâche planifiée Windows)
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_pdfs": len(pdfs),
        "processed": sum(1 for r in results if r["status"] == "success"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
    STATUS_FILE.parent.mkdir(exist_ok=True)
    STATUS_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Statut écrit: {STATUS_FILE}")
    logger.info(f"Résumé: {summary['processed']} success, {summary['skipped']} skipped, {summary['errors']} errors")

    return summary


if __name__ == "__main__":
    result = ingest_hss_batch()
    sys.exit(0 if result.get("ok", result.get("errors", 0) == 0) else 1)

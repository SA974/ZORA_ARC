"""Orchestration de l'ingestion PDF (façade -> app.services.document_ingestion)."""
from app.services.document_ingestion import (  # noqa: F401
    get_embedder,
    ingest_folder,
    ingest_pdf_file,
    resolve_domain,
)

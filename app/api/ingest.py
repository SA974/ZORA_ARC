from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, HTTPException
from psycopg.types.json import Jsonb

from app.db import get_connection
from app.models.schemas import DocumentIngestRequest, FolderIngestRequest, PdfIngestRequest
from app.services.document_ingestion import ingest_folder, ingest_pdf_file
from app.services.embedding_service import EmbeddingService, to_pgvector
from app.services.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def chunk_text(text: str, size: int = 1200, overlap: int = 120) -> list[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


@router.post("/pdf")
async def ingest_pdf(request: PdfIngestRequest) -> dict:
    """Lit un PDF, l'assainit, le découpe, l'embedde et le stocke dans `zora` (base unique)."""
    result = ingest_pdf_file(
        request.path,
        request.domain,
        dry_run=request.dry_run,
        max_pages=request.max_pages,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/folder")
async def ingest_folder_endpoint(request: FolderIngestRequest) -> dict:
    """Ingère récursivement un dossier de PDFs dans `zora` (opération longue)."""
    summary = ingest_folder(
        request.path,
        fallback_domain=request.domain,
        max_file_mb=request.max_file_mb,
        max_pages=request.max_pages,
        limit=request.limit,
        dry_run=request.dry_run,
        post_embed_delay=request.post_embed_delay,
    )
    return summary


@router.post("/document")
async def ingest_document(request: DocumentIngestRequest) -> dict:
    pieces = chunk_text(request.content)
    content_hash = hashlib.sha256(request.content.encode("utf-8")).hexdigest()

    # Vectorisation des chunks (passage). Repli propre si provider absent/indisponible.
    embedder = EmbeddingService()
    embeddings: list[list[float]] | None = None
    embedding_status = "skipped_provider_not_configured"
    if embedder.configured() and pieces:
        try:
            embeddings = embedder.embed_texts(pieces, input_type="passage")
            embedding_status = "embedded"
        except Exception as exc:  # noqa: BLE001
            logger.warning("ingestion sans embeddings (provider indisponible): %s", type(exc).__name__)
            embedding_status = "failed_provider_error"

    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into zora.documents(title, source_uri, content_hash, metadata)
                values (%s, %s, %s, %s::jsonb)
                returning id
                """,
                (request.title, request.source_uri, content_hash, Jsonb(request.metadata)),
            )
            document_id = cur.fetchone()["id"]
            for ordinal, content in enumerate(pieces):
                vec = embeddings[ordinal] if embeddings is not None else None
                cur.execute(
                    """
                    insert into zora.chunks(document_id, ordinal, content, embedding, metadata)
                    values (%s, %s, %s, %s::vector, '{}'::jsonb)
                    on conflict (document_id, ordinal) do nothing
                    """,
                    (document_id, ordinal, content, to_pgvector(vec) if vec is not None else None),
                )
            conn.commit()
            chunk_rows = []
            if request.extract:
                cur.execute(
                    "select id, content from zora.chunks where document_id = %s order by ordinal",
                    (document_id,),
                )
                chunk_rows = [(str(r["id"]), r["content"]) for r in cur.fetchall()]

        extraction = None
        if request.extract:
            pipeline = IngestionPipeline()
            if not pipeline.configured():
                extraction = {"status": "skipped_provider_not_configured"}
            else:
                entities = facts = 0
                conflicts = 0
                for chunk_id, content in chunk_rows:
                    try:
                        res = pipeline.extract_and_store(
                            content,
                            source_document_id=str(document_id),
                            source_chunk_id=chunk_id,
                            detect_conflicts=request.detect_conflicts,
                        )
                        entities += res["entities"]
                        facts += res["facts"]
                        conflicts += len(res["conflicts"])
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("extraction chunk %s ignorée: %s", chunk_id, type(exc).__name__)
                extraction = {"status": "done", "entities": entities, "facts": facts, "conflicts": conflicts}

        return {
            "ok": True,
            "document_id": str(document_id),
            "chunks": len(pieces),
            "embedding_status": embedding_status,
            "embedding_model": embedder.settings.embedding_model if embeddings is not None else None,
            "memgraph_extraction": extraction or {"status": "not_requested"},
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"ok": False, "error": str(exc)}) from exc

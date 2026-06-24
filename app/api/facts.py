from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import ExtractRequest, FactCreateRequest, FeedbackRequest, SyncHindsightRequest
from app.services.hindsight_sync import HindsightGraphSync
from app.services.ingestion_pipeline import IngestionPipeline
from app.services.temporal_service import TemporalService

router = APIRouter(prefix="/facts", tags=["facts"])


@router.post("/sync-hindsight")
async def sync_hindsight(request: SyncHindsightRequest) -> dict:
    sync = HindsightGraphSync()
    if not sync.configured():
        raise HTTPException(status_code=503, detail={"ok": False, "error": "Hindsight et/ou LLM non configurés"})
    return sync.sync(min_len=request.min_len, limit=request.limit, detect_conflicts=request.detect_conflicts)


@router.post("/extract")
async def extract_facts(request: ExtractRequest) -> dict:
    pipeline = IngestionPipeline()
    if not pipeline.configured():
        raise HTTPException(status_code=503, detail={"ok": False, "error": "LLM provider non configuré"})
    try:
        return pipeline.extract_and_store(
            text=request.text,
            source_document_id=request.source_document_id,
            source_chunk_id=request.source_chunk_id,
            observed_at=request.observed_at,
            detect_conflicts=request.detect_conflicts,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"ok": False, "error": str(exc)}) from exc


@router.post("")
async def create_fact(request: FactCreateRequest) -> dict:
    try:
        fact = TemporalService().add_fact(
            subject=request.subject,
            predicate=request.predicate,
            object_value=request.object_value,
            provenance_text=request.provenance_text,
            source_document_id=request.source_document_id,
            source_chunk_id=request.source_chunk_id,
            confidence=request.confidence,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            observed_at=request.observed_at,
        )
        return {"ok": True, "fact": fact}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"ok": False, "error": str(exc)}) from exc


@router.post("/{fact_id}/feedback")
async def fact_feedback(fact_id: str, request: FeedbackRequest) -> dict:
    try:
        return TemporalService().record_feedback(fact_id, request.signal, request.source, request.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"ok": False, "error": str(exc)}) from exc


@router.post("/{fact_id}/detect-conflict")
async def fact_detect_conflict(fact_id: str) -> dict:
    try:
        return TemporalService().detect_temporal_conflict(fact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "error": str(exc)}) from exc


@router.get("/active")
async def active_facts(query: str, limit: int = 8) -> dict:
    return {"ok": True, "facts": TemporalService().active_facts_for_query(query, limit)}

from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import RetrieveRequest
from app.services.hindsight_client import HindsightClient
from app.services.retrieval_service import RetrievalService
from app.services.zora_arc_service import ZoraArcService

router = APIRouter(tags=["retrieve"])


@router.post("/retrieve")
async def retrieve(request: RetrieveRequest) -> dict:
    zora = ZoraArcService()
    taskcard = zora.build_taskcard(request.query, request.expected_evidence_level)
    route_score = zora.score_router(request.query, request.expected_evidence_level)
    hindsight = await HindsightClient().recall(request.query, request.limit)
    memories = hindsight.get("memories", []) if hindsight.get("ok") else []
    bundle = RetrievalService().build_context_bundle(request.query, memories, request.limit)
    if not hindsight.get("ok"):
        bundle.warnings.append(f"Hindsight unavailable: {hindsight.get('error', 'not configured')}")
    return {
        "ok": True,
        "taskcard": taskcard.model_dump(),
        "zora_router": route_score,
        "context_bundle": bundle.model_dump(),
    }

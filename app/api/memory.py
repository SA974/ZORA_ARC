from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import RecallRequest, RetainRequest
from app.services.hindsight_client import HindsightClient

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/retain")
async def retain(request: RetainRequest) -> dict:
    result = await HindsightClient().retain(request.text, request.metadata)
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result)
    return result


@router.post("/recall")
async def recall(request: RecallRequest) -> dict:
    result = await HindsightClient().recall(request.query, request.limit)
    if not result.get("ok"):
        return {"ok": False, "context": [], "warning": result.get("error", "Hindsight unavailable")}
    return {"ok": True, "context": result.get("memories", [])}

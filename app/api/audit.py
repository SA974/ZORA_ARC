from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import AuditRequest
from app.services.zora_arc_service import ZoraArcService

router = APIRouter(tags=["audit"])


@router.post("/audit")
async def audit(request: AuditRequest) -> dict:
    payload = request.model_dump()
    result = ZoraArcService().audit_answer(payload)
    return {"ok": result["ok"], "findings": result["findings"], "taskcard_checked": bool(request.taskcard)}

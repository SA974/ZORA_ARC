from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.db import check_database_health
from app.services.hindsight_client import HindsightClient
from app.services.provider_health import check_ollama

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    hindsight = await HindsightClient(settings).health()
    return {
        "app": {"name": "ARC-MEM Bridge", "version": "0.1", "env": settings.arc_mem_env},
        "postgres": check_database_health(settings).as_dict(),
        "ollama": check_ollama(),
        "hindsight": hindsight,
    }

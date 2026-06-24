from __future__ import annotations

from fastapi import FastAPI

from app.api import audit, facts, health, ingest, memory, retrieve
from app.logging_config import configure_logging
from app.routes import monitoring

configure_logging()

app = FastAPI(
    title="ARC-MEM Bridge",
    version="0.1",
    description="Local integration layer for Hermes, Hindsight, MemGraphRAG, H-MEM and PostgreSQL.",
)

app.include_router(health.router)
app.include_router(memory.router)
app.include_router(ingest.router)
app.include_router(retrieve.router)
app.include_router(audit.router)
app.include_router(facts.router)
app.include_router(monitoring.router)

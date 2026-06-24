"""Healthchecks (façade -> app.db + app.services.provider_health)."""
from app.db import check_database_health  # noqa: F401
from app.services.provider_health import check_ollama, preflight_embedder  # noqa: F401

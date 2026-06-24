from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


SECRET_KEYS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASS")

# Résolution absolue du .env (racine du dépôt = parent de app/) pour ne pas dépendre
# du répertoire de lancement (uvicorn, CLI, junction desktop, tests...).
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def mask_secret(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def sanitize_mapping(values: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in values.items():
        upper = key.upper()
        if any(marker in upper for marker in SECRET_KEYS):
            raw = value.get_secret_value() if isinstance(value, SecretStr) else value
            sanitized[key] = mask_secret(raw)
        else:
            sanitized[key] = value
    return sanitized


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    arc_mem_env: str = "local"
    arc_mem_host: str = "127.0.0.1"
    arc_mem_port: int = 8791

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "rag_arc"
    postgres_user: str = "postgres"
    postgres_password: SecretStr = Field(default=SecretStr(""))
    postgres_sslmode: str = "disable"

    hindsight_mode: str = "external"
    hindsight_base_url: str = "http://127.0.0.1:PORT_A_CONFIRMER"
    hindsight_api_key: SecretStr = Field(default=SecretStr(""))
    hindsight_database_url: SecretStr = Field(default=SecretStr(""))

    # Provider LLM principal : Ollama (endpoint OpenAI-compatible local). Aucune dépendance
    # NVIDIA NIM / OpenRouter. Les valeurs ci-dessous sont des défauts sûrs surchargés par .env.
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: SecretStr = Field(default=SecretStr("ollama"))
    llm_model: str = "qwen:14b"
    # Modèle dédié à l'extraction entités/relations : instruct local servant du JSON propre.
    extraction_model: str = "qwen:14b"

    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    embedding_base_url: str = "http://localhost:11434/v1"
    embedding_api_key: SecretStr = Field(default=SecretStr("ollama"))
    embedding_batch_size: int = 64
    embedding_timeout: int = 30
    postgres_connect_timeout: int = 3

    def postgres_dsn(self, database: str | None = None) -> str:
        password = self.postgres_password.get_secret_value()
        auth = self.postgres_user
        if password:
            auth = f"{self.postgres_user}:{password}"
        db = database or self.postgres_db
        return (
            f"postgresql://{auth}@{self.postgres_host}:{self.postgres_port}/{db}"
            f"?sslmode={self.postgres_sslmode}&connect_timeout={self.postgres_connect_timeout}"
        )

    def public_dict(self) -> dict[str, Any]:
        return sanitize_mapping(self.model_dump())


@lru_cache
def get_settings() -> Settings:
    return Settings()

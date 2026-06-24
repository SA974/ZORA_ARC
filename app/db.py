from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import Settings, get_settings, mask_secret

logger = logging.getLogger(__name__)

REQUIRED_EXTENSIONS = ("vector", "postgis", "pg_trgm", "pgcrypto")


@dataclass
class DatabaseHealth:
    ok: bool
    database: str
    server_version: str | None
    extensions: dict[str, bool]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "database": self.database,
            "server_version": self.server_version,
            "extensions": self.extensions,
            "error": self.error,
        }


def get_connection(settings: Settings | None = None, database: str | None = None):
    cfg = settings or get_settings()
    logger.debug(
        "Opening PostgreSQL connection host=%s port=%s db=%s user=%s password=%s",
        cfg.postgres_host,
        cfg.postgres_port,
        database or cfg.postgres_db,
        cfg.postgres_user,
        mask_secret(cfg.postgres_password.get_secret_value()),
    )
    return psycopg.connect(cfg.postgres_dsn(database), row_factory=dict_row)


def test_connection(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    with get_connection(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database() as database, version() as version")
            row = cur.fetchone() or {}
    return {"ok": True, "database": row.get("database"), "version": row.get("version")}


def available_databases(settings: Settings | None = None) -> list[str]:
    cfg = settings or get_settings()
    with get_connection(cfg, database="postgres") as conn:
        with conn.cursor() as cur:
            cur.execute("select datname from pg_database where datistemplate = false order by datname")
            return [row["datname"] for row in cur.fetchall()]


def check_extensions(settings: Settings | None = None) -> dict[str, bool]:
    cfg = settings or get_settings()
    with get_connection(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute("select extname from pg_extension")
            installed = {row["extname"] for row in cur.fetchall()}
    return {name: name in installed for name in REQUIRED_EXTENSIONS}


def check_available_extensions(settings: Settings | None = None) -> dict[str, bool]:
    cfg = settings or get_settings()
    with get_connection(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select name from pg_available_extensions where name = any(%s)",
                (list(REQUIRED_EXTENSIONS),),
            )
            available = {row["name"] for row in cur.fetchall()}
    return {name: name in available for name in REQUIRED_EXTENSIONS}


def check_database_health(settings: Settings | None = None) -> DatabaseHealth:
    cfg = settings or get_settings()
    try:
        with get_connection(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("select current_database() as database, version() as version")
                row = cur.fetchone() or {}
                cur.execute("select extname from pg_extension")
                installed = {item["extname"] for item in cur.fetchall()}
        return DatabaseHealth(
            ok=True,
            database=str(row.get("database") or cfg.postgres_db),
            server_version=str(row.get("version") or ""),
            extensions={name: name in installed for name in REQUIRED_EXTENSIONS},
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics must not crash callers.
        return DatabaseHealth(
            ok=False,
            database=cfg.postgres_db,
            server_version=None,
            extensions={name: False for name in REQUIRED_EXTENSIONS},
            error=str(exc),
        )

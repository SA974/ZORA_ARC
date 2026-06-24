from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import Settings, get_settings, mask_secret

logger = logging.getLogger(__name__)


class HindsightClient:
    def __init__(self, settings: Settings | None = None, timeout: float = 2.0) -> None:
        self.settings = settings or get_settings()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        if self.settings.hindsight_mode == "postgresql_direct":
            return bool(self.settings.hindsight_database_url.get_secret_value())
        url = self.settings.hindsight_base_url
        parsed = urlparse(url)
        try:
            port = parsed.port
        except ValueError:
            return False
        return bool(url and parsed.scheme in {"http", "https"} and parsed.hostname and port)

    def _headers(self) -> dict[str, str]:
        key = self.settings.hindsight_api_key.get_secret_value()
        return {"Authorization": f"Bearer {key}"} if key else {}

    async def health(self) -> dict[str, Any]:
        if self.settings.hindsight_mode == "postgresql_direct":
            return self._direct_health()
        if not self.configured:
            return {"ok": False, "configured": False, "error": "Hindsight base URL not configured"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.settings.hindsight_base_url.rstrip('/')}/health", headers=self._headers())
            return {"ok": response.is_success, "status_code": response.status_code}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "configured": True, "error": str(exc) or repr(exc)}

    async def retain(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.settings.hindsight_mode == "postgresql_direct":
            return self._direct_retain(text, metadata)
        if not self.configured:
            return {"ok": False, "error": "Hindsight not configured"}
        payload = {"text": text, "metadata": metadata or {}}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.settings.hindsight_base_url.rstrip('/')}/memory/retain",
                    json=payload,
                    headers=self._headers(),
                )
            return {"ok": response.is_success, "status_code": response.status_code, "data": response.json() if response.content else None}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Hindsight retain failed: %s", mask_secret(str(exc)))
            return {"ok": False, "error": str(exc)}

    async def recall(self, query: str, limit: int = 5) -> dict[str, Any]:
        if self.settings.hindsight_mode == "postgresql_direct":
            return self._direct_recall(query, limit)
        if not self.configured:
            return {"ok": False, "memories": [], "error": "Hindsight not configured"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.settings.hindsight_base_url.rstrip('/')}/memory/recall",
                    json={"query": query, "limit": limit},
                    headers=self._headers(),
                )
            data = response.json() if response.content else {}
            return {"ok": response.is_success, "memories": data.get("memories", data)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "memories": [], "error": str(exc)}

    async def reflect(self, topic: str, scope: str = "project") -> dict[str, Any]:
        if self.settings.hindsight_mode == "postgresql_direct":
            recalled = self._direct_recall(topic, limit=10)
            return {"ok": recalled.get("ok", False), "scope": scope, "data": recalled.get("memories", [])}
        if not self.configured:
            return {"ok": False, "error": "Hindsight not configured"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.settings.hindsight_base_url.rstrip('/')}/memory/reflect",
                    json={"topic": topic, "scope": scope},
                    headers=self._headers(),
                )
            return {"ok": response.is_success, "data": response.json() if response.content else None}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def _direct_dsn(self) -> str:
        return self.settings.hindsight_database_url.get_secret_value()

    def _direct_health(self) -> dict[str, Any]:
        if not self._direct_dsn():
            return {
                "ok": False,
                "configured": False,
                "mode": "postgresql_direct",
                "error": "Hindsight database URL not configured",
            }
        try:
            with psycopg.connect(self._direct_dsn(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("select count(*) as facts from facts")
                    facts = cur.fetchone()["facts"]
                    cur.execute("select count(*) as sessions from sessions")
                    sessions = cur.fetchone()["sessions"]
                    cur.execute("select count(*) as entities from entities")
                    entities = cur.fetchone()["entities"]
            return {
                "ok": True,
                "configured": True,
                "mode": "postgresql_direct",
                "facts": facts,
                "sessions": sessions,
                "entities": entities,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "configured": True, "mode": "postgresql_direct", "error": str(exc) or repr(exc)}

    def _direct_retain(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._direct_dsn():
            return {"ok": False, "mode": "postgresql_direct", "error": "Hindsight database URL not configured"}
        metadata = metadata or {}
        fact_type = str(metadata.get("type") or "observation")
        try:
            with psycopg.connect(self._direct_dsn(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select column_name
                        from information_schema.columns
                        where table_name = 'facts'
                        """
                    )
                    columns = {row["column_name"] for row in cur.fetchall()}
                    insert_columns = ["content", "fact_type", "metadata"]
                    values: list[Any] = [text, fact_type, Jsonb(metadata)]
                    if "document_id" in columns:
                        insert_columns.append("document_id")
                        values.append(None)
                    elif "doc_id" in columns:
                        insert_columns.append("doc_id")
                        values.append(None)
                    placeholders = ", ".join(["%s"] * len(insert_columns))
                    cur.execute(
                        f"""
                        insert into facts({", ".join(insert_columns)})
                        values ({placeholders})
                        returning id
                        """,
                        values,
                    )
                    row = cur.fetchone()
                conn.commit()
            return {"ok": True, "mode": "postgresql_direct", "id": str(row["id"])}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "mode": "postgresql_direct", "error": str(exc) or repr(exc)}

    def _direct_recall(self, query: str, limit: int = 5) -> dict[str, Any]:
        if not self._direct_dsn():
            return {"ok": False, "mode": "postgresql_direct", "memories": [], "error": "Hindsight database URL not configured"}
        try:
            with psycopg.connect(self._direct_dsn(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select id, content, fact_type, metadata, created_at
                        from facts
                        where content ilike %s or metadata::text ilike %s
                        order by created_at desc
                        limit %s
                        """,
                        (f"%{query}%", f"%{query}%", limit),
                    )
                    memories = [dict(row) for row in cur.fetchall()]
            return {"ok": True, "mode": "postgresql_direct", "memories": memories}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "mode": "postgresql_direct", "memories": [], "error": str(exc) or repr(exc)}

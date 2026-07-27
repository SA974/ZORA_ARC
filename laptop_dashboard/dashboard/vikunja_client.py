from __future__ import annotations

import datetime as dt
from typing import Any

import requests


class VikunjaError(RuntimeError):
    """Erreur de communication avec l'API Vikunja (jeton expiré, projet introuvable, réseau...)."""


class VikunjaClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._session.request(
                method, f"{self.base_url}/api/v1{path}", timeout=self.timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise VikunjaError(f"Impossible de joindre Vikunja ({self.base_url}) : {exc}") from exc
        if resp.status_code == 401:
            raise VikunjaError(
                "Jeton Vikunja invalide ou expiré — régénère-le dans "
                "Vikunja > Paramètres > Jetons API et mets à jour le .env."
            )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise VikunjaError(f"Erreur Vikunja {resp.status_code} sur {path} : {exc}") from exc
        return resp.json() if resp.content else None

    def list_projects(self) -> list[dict]:
        return self._request("GET", "/projects")

    def list_open_tasks(self) -> list[dict]:
        tasks = self._request("GET", "/tasks/all") or []
        return [t for t in tasks if not t.get("done")]

    def week_agenda(self, tasks: list[dict]) -> dict[str, list[dict]]:
        """Regroupe les tâches dont l'échéance tombe dans la semaine en cours (lundi-dimanche)."""
        today = dt.date.today()
        monday = today - dt.timedelta(days=today.weekday())
        sunday = monday + dt.timedelta(days=6)
        by_day: dict[str, list[dict]] = {}
        for task in tasks:
            due_raw = task.get("due_date")
            if not due_raw or due_raw.startswith("0001-01-01"):
                continue
            due = dt.date.fromisoformat(due_raw[:10])
            if monday <= due <= sunday:
                by_day.setdefault(due.isoformat(), []).append(task)
        return by_day

    def find_project_id(self, name: str) -> int | None:
        for project in self.list_projects():
            if project.get("title", "").strip().lower() == name.strip().lower():
                return project.get("id")
        return None

    def create_task(self, project_id: int, title: str) -> dict:
        return self._request("PUT", f"/projects/{project_id}/tasks", json={"title": title})

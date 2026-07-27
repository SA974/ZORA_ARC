from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import webview

from .calendar_client import GoogleCalendarClient
from .config import load_settings
from .vikunja_client import VikunjaClient, VikunjaError

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
DAY_NAMES_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _build_week(vikunja_days: dict[str, list[dict]], calendar_events: list[dict]) -> list[dict]:
    today = dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    week = []
    for i in range(7):
        day = monday + dt.timedelta(days=i)
        iso = day.isoformat()
        entries = [
            {"title": t.get("title"), "source": "Vikunja"} for t in vikunja_days.get(iso, [])
        ]
        entries += [e for e in calendar_events if e.get("date") == iso]
        week.append(
            {
                "label": DAY_NAMES_FR[i],
                "date": day.strftime("%d/%m"),
                "is_today": day == today,
                "entries": entries,
            }
        )
    return week


class Api:
    """Pont exposé au JavaScript de la fenêtre (pywebview js_api)."""

    def __init__(self, vikunja: VikunjaClient, night_project_name: str):
        self._vikunja = vikunja
        self._night_project_name = night_project_name
        self._night_project_id: int | None = None

    def _resolve_night_project(self) -> int:
        if self._night_project_id is None:
            project_id = self._vikunja.find_project_id(self._night_project_name)
            if project_id is None:
                raise VikunjaError(
                    f"Projet Vikunja « {self._night_project_name} » introuvable — "
                    "vérifie VIKUNJA_NIGHT_PROJECT dans .env."
                )
            self._night_project_id = project_id
        return self._night_project_id

    def add_night_task(self, title: str) -> dict:
        title = (title or "").strip()
        if not title:
            return {"ok": False, "error": "Le titre de la tâche est vide."}
        try:
            project_id = self._resolve_night_project()
            self._vikunja.create_task(project_id, title)
            return {"ok": True}
        except VikunjaError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # remonté tel quel à l'UI pour affichage
            return {"ok": False, "error": f"Erreur inattendue : {exc}"}


def gather_dashboard_data() -> tuple[dict, VikunjaClient, object]:
    settings = load_settings()
    vikunja = VikunjaClient(settings.vikunja_url, settings.vikunja_token)
    calendar = GoogleCalendarClient(settings.google_credentials_path, settings.google_token_path)

    error = None
    open_tasks: list[dict] = []
    week_days: list[dict] = []
    try:
        open_tasks = vikunja.list_open_tasks()
        agenda = vikunja.week_agenda(open_tasks)
        week_days = _build_week(agenda, calendar.week_events())
    except VikunjaError as exc:
        error = str(exc)

    undated_tasks = [
        t for t in open_tasks if not t.get("due_date") or t["due_date"].startswith("0001-01-01")
    ]

    data = {
        "error": error,
        "week": week_days,
        "tasks": [{"title": t.get("title")} for t in undated_tasks],
        "generated_at": dt.datetime.now().strftime("%A %d %B %Y, %H:%M"),
    }
    return data, vikunja, settings


def main() -> None:
    data, vikunja, settings = gather_dashboard_data()
    api = Api(vikunja, settings.night_project_name)

    window = webview.create_window(
        "DENUDATA.IO — Bonjour Stéphane",
        str(UI_DIR / "index.html"),
        js_api=api,
        width=1150,
        height=800,
        background_color="#050505",
    )

    def inject_data() -> None:
        window.evaluate_js(f"window.renderDashboard({json.dumps(data)})")

    webview.start(inject_data, debug=False)


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Settings:
    vikunja_url: str
    vikunja_token: str
    night_project_name: str
    google_credentials_path: str | None
    google_token_path: str | None


def load_settings() -> Settings:
    vikunja_url = os.environ.get("VIKUNJA_URL", "").strip()
    vikunja_token = os.environ.get("VIKUNJA_API_TOKEN", "").strip()
    if not vikunja_url or not vikunja_token:
        raise RuntimeError(
            "VIKUNJA_URL et VIKUNJA_API_TOKEN doivent être renseignés dans "
            "laptop_dashboard/.env (copier .env.example)."
        )
    return Settings(
        vikunja_url=vikunja_url,
        vikunja_token=vikunja_token,
        night_project_name=os.environ.get("VIKUNJA_NIGHT_PROJECT", "Inbox").strip() or "Inbox",
        google_credentials_path=os.environ.get("GOOGLE_CALENDAR_CREDENTIALS") or None,
        google_token_path=os.environ.get("GOOGLE_CALENDAR_TOKEN") or None,
    )

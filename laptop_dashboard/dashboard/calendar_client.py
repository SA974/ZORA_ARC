from __future__ import annotations

"""Intégration Google Calendar.

Étape suivante (pas encore câblée) : utiliser google-api-python-client avec un
flux OAuth exécuté une fois sur le poste local (fenêtre de consentement dans le
navigateur), puis réutiliser le token rafraîchi automatiquement.

En attendant, ce client renvoie une liste vide : le tableau de bord fonctionne
déjà avec les seules données Vikunja.
"""


class GoogleCalendarClient:
    def __init__(self, credentials_path: str | None, token_path: str | None):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.enabled = bool(credentials_path)

    def week_events(self) -> list[dict]:
        if not self.enabled:
            return []
        # TODO: brancher google-api-python-client une fois les credentials OAuth fournis.
        # Chaque événement doit avoir la forme {"date": "YYYY-MM-DD", "title": str, "source": "Google Calendar"}.
        return []

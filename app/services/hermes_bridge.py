from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class HermesBridge:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home or self._detect_home()
        self.hermes_dir = self.home / ".hermes"
        self.config_path = self.hermes_dir / "config.yaml"

    def _detect_home(self) -> Path:
        candidates = [
            Path.home(),
            Path("/mnt/c/Users/Stephane_Arnoux"),
        ]
        for candidate in candidates:
            if (candidate / ".hermes" / "config.yaml").exists():
                return candidate
        for candidate in candidates:
            if (candidate / ".hermes").exists():
                return candidate
        return Path.home()

    def diagnose(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "hermes_dir": str(self.hermes_dir),
            "hermes_dir_exists": self.hermes_dir.exists(),
            "config_path": str(self.config_path),
            "config_exists": self.config_path.exists(),
            "active_provider": None,
            "memory_provider": None,
            "hindsight_config": None,
            "recommendations": [],
        }
        if self.config_path.exists():
            text = self.config_path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("provider:") and result["active_provider"] is None:
                    result["active_provider"] = stripped.split(":", 1)[1].strip().strip("'\"")
                if "hindsight" in stripped.lower():
                    result["memory_provider"] = "hindsight-reference-detected"
        hindsight_config = self.hermes_dir / "hindsight" / "config.json"
        if hindsight_config.exists():
            try:
                data = json.loads(hindsight_config.read_text(encoding="utf-8"))
                result["hindsight_config"] = {
                    "path": str(hindsight_config),
                    "mode": data.get("mode"),
                    "memory_mode": data.get("memory_mode"),
                    "embedded_postgres": data.get("embedded_postgres"),
                    "database_url_configured": bool(data.get("database_url")),
                    "llm_provider": data.get("llm_provider"),
                    "llm_model": data.get("llm_model"),
                    "llm_base_url": data.get("llm_base_url"),
                }
            except Exception as exc:  # noqa: BLE001
                result["hindsight_config"] = {"path": str(hindsight_config), "error": str(exc)}
        if not result["config_exists"]:
            result["recommendations"].append("Install or initialize Hermes before direct integration.")
        result["recommendations"].append("Do not edit config.yaml automatically; create a timestamped backup and review a diff first.")
        return result

    def proposed_backup_path(self) -> str:
        import datetime as dt

        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(self.config_path.with_name(f"config.yaml.arc-mem-backup-{stamp}"))

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import check_available_extensions, check_database_health  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402


def main() -> int:
    configure_logging()
    health = check_database_health()
    payload = {"health": health.as_dict()}
    if health.ok:
        payload["available_extensions"] = check_available_extensions()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if health.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

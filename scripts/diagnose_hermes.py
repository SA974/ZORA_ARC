from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.hermes_bridge import HermesBridge  # noqa: E402


def main() -> int:
    print(json.dumps(HermesBridge().diagnose(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

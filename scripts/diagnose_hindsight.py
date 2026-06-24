from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.hindsight_client import HindsightClient  # noqa: E402


async def run() -> int:
    print(json.dumps(await HindsightClient().health(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import check_database_health  # noqa: E402
from app.services.hmem_router import HMemRouter  # noqa: E402
from app.services.zora_arc_service import ZoraArcService  # noqa: E402


def main() -> int:
    query = "test ARC-MEM Bridge PostgreSQL Hindsight MemGraphRAG"
    payload = {
        "postgres": check_database_health().as_dict(),
        "route": HMemRouter().route_query(query),
        "zora": ZoraArcService().score_router(query),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

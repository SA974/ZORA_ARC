from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logging_config import configure_logging  # noqa: E402
from app.services.hindsight_sync import HindsightGraphSync  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise la mémoire agentique Hindsight vers le graphe MemGraphRAG (idempotent)."
    )
    parser.add_argument("--limit", type=int, default=0, help="Nb max de souvenirs (0 = tous les en attente).")
    parser.add_argument("--min-len", type=int, default=25, help="Longueur min du contenu pour extraire.")
    parser.add_argument("--detect-conflicts", action="store_true", help="Active la supersession temporelle.")
    parser.add_argument("--dry-run", action="store_true", help="Liste les souvenirs en attente sans extraire.")
    args = parser.parse_args()
    configure_logging()

    sync = HindsightGraphSync()
    if not sync.configured():
        print("ERREUR: Hindsight et/ou LLM non configurés (.env).", file=sys.stderr)
        return 2

    if args.dry_run:
        pending = sync.pending_facts(min_len=args.min_len, limit=args.limit)
        print(f"souvenirs en attente: {len(pending)}", flush=True)
        for f in pending[:20]:
            print(f"  {str(f['id'])[:8]}  {f['content'][:80]}")
        return 0

    started = time.time()
    result = sync.sync(min_len=args.min_len, limit=args.limit, detect_conflicts=args.detect_conflicts)
    result["duration_seconds"] = round(time.time() - started, 1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())

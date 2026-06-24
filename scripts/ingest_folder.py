#!/usr/bin/env python3
"""Ingestion récursive d'un dossier de PDF dans `zora` via ARC-MEM Bridge (base unique).

Exemples :
    python scripts/ingest_folder.py "F:\\...\\HOMO_SAPIENS_SAPIENS\\PHILOSOPHIE" --limit 5
    python scripts/ingest_folder.py "F:\\...\\HOMO_SAPIENS_SAPIENS" --report ingestion_zora.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logging_config import configure_logging  # noqa: E402
from app.services.document_ingestion import ingest_folder  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingestion récursive de PDF dans zora")
    parser.add_argument("root", help="dossier racine à scanner")
    parser.add_argument("--domain", default="bibliotheque", help="domaine par défaut si non déduit du chemin")
    parser.add_argument("--limit", type=int, default=0, help="limiter au N premiers PDF (0 = tous)")
    parser.add_argument("--max-pages", type=int, default=1500)
    parser.add_argument("--max-file-mb", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.0, help="délai (s) après chaque embedding API (pour free endpoints)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default=None, help="chemin du rapport JSON")
    args = parser.parse_args(argv)

    configure_logging()
    summary = ingest_folder(
        args.root,
        fallback_domain=args.domain,
        max_file_mb=args.max_file_mb,
        max_pages=args.max_pages,
        limit=args.limit,
        dry_run=args.dry_run,
        report_path=args.report,
        post_embed_delay=args.delay,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "details"}, indent=2, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

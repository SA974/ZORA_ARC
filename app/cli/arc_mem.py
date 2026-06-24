from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from app.db import check_database_health
from app.services.hermes_bridge import HermesBridge
from app.services.hindsight_client import HindsightClient

ROOT = Path(__file__).resolve().parents[2]


def run_script(name: str, *args: str) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / name), *args]
    return subprocess.call(cmd)


async def hindsight_health() -> dict:
    return await HindsightClient().health()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arc-mem")
    parser.add_argument(
        "command",
        choices=[
            "health", "check-postgres", "apply-migrations", "diagnose-hermes",
            "diagnose-hindsight", "smoke-test", "ingest-pdf", "ingest-folder",
        ],
    )
    parser.add_argument("path", nargs="?", help="PDF (ingest-pdf) ou dossier (ingest-folder)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--domain", default="bibliotheque")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-pages", type=int, default=1500)
    parser.add_argument("--max-file-mb", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.0, help="délai (s) entre appels API (free endpoints)")
    parser.add_argument("--report", help="chemin du rapport JSON (ingest-folder)")
    args = parser.parse_args(argv)

    if args.command in ("ingest-pdf", "ingest-folder") and not args.path:
        parser.error(f"{args.command} requiert un chemin")

    if args.command == "health":
        payload = {"postgres": check_database_health().as_dict(), "hindsight": asyncio.run(hindsight_health())}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload["postgres"]["ok"] else 2
    if args.command == "check-postgres":
        return run_script("check_postgres.py")
    if args.command == "apply-migrations":
        return run_script("apply_migrations.py", "--dry-run") if args.dry_run else run_script("apply_migrations.py")
    if args.command == "diagnose-hermes":
        print(json.dumps(HermesBridge().diagnose(), indent=2, ensure_ascii=False))
        return 0
    if args.command == "diagnose-hindsight":
        print(json.dumps(asyncio.run(hindsight_health()), indent=2, ensure_ascii=False))
        return 0
    if args.command == "smoke-test":
        return run_script("smoke_test.py")
    if args.command == "ingest-pdf":
        from app.services.document_ingestion import ingest_pdf_file

        result = ingest_pdf_file(args.path, args.domain, dry_run=args.dry_run, max_pages=args.max_pages)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 2
    if args.command == "ingest-folder":
        from app.services.document_ingestion import ingest_folder

        summary = ingest_folder(
            args.path,
            fallback_domain=args.domain,
            max_file_mb=args.max_file_mb,
            max_pages=args.max_pages,
            limit=args.limit,
            dry_run=args.dry_run,
            report_path=args.report,
            post_embed_delay=args.delay,
        )
        summary_view = {k: v for k, v in summary.items() if k != "details"}
        print(json.dumps(summary_view, indent=2, ensure_ascii=False))
        return 0 if summary["failed"] == 0 else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

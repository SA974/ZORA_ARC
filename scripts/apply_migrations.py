#!/usr/bin/env python3
"""Runner de migrations SQL versionné et idempotent.

Améliore l'ancien runner (qui rejouait TOUS les fichiers à chaque exécution) :
- un registre `public.schema_migrations` trace les migrations déjà appliquées ;
- seules les migrations absentes du registre sont exécutées, chacune dans SA transaction ;
- `--dry-run`   : liste ce qui serait appliqué, sans rien exécuter ;
- `--baseline`  : marque TOUTES les migrations présentes comme déjà appliquées SANS les
                  exécuter (pour adopter le registre sur une base déjà migrée).

Usage :
    python scripts/apply_migrations.py --dry-run
    python scripts/apply_migrations.py --baseline     # 1re adoption sur base existante
    python scripts/apply_migrations.py                # applique les nouvelles migrations
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "app" / "migrations"

REGISTRY_DDL = """
create table if not exists public.schema_migrations (
  filename   text primary key,
  checksum   text not null,
  applied_at timestamptz not null default now()
)
"""


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied_set(cur) -> set[str]:
    cur.execute("select filename from public.schema_migrations")
    return {r["filename"] for r in cur.fetchall()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Runner de migrations SQL versionné")
    parser.add_argument("--dry-run", action="store_true", help="Liste sans exécuter.")
    parser.add_argument("--baseline", action="store_true",
                        help="Marque toutes les migrations comme appliquées sans les exécuter.")
    args = parser.parse_args(argv)
    configure_logging()

    files = migration_files()
    if not files:
        print("Aucune migration trouvée.")
        return 0

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(REGISTRY_DDL)
            conn.commit()

            with conn.cursor() as cur:
                done = applied_set(cur)
            pending = [f for f in files if f.name not in done]

            if args.dry_run:
                for f in files:
                    print(("APPLIED " if f.name in done else "PENDING ") + f.name)
                print(f"\n{len(pending)} migration(s) en attente.")
                return 0

            if args.baseline:
                with conn.cursor() as cur:
                    for f in pending:
                        cur.execute(
                            "insert into public.schema_migrations(filename, checksum) values (%s, %s) "
                            "on conflict (filename) do nothing",
                            (f.name, checksum(f)),
                        )
                conn.commit()
                print(f"BASELINE : {len(pending)} migration(s) marquée(s) appliquée(s) sans exécution.")
                return 0

            if not pending:
                print("À jour : aucune migration à appliquer.")
                return 0

            for f in pending:
                sql = f.read_text(encoding="utf-8")
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(sql)
                        cur.execute(
                            "insert into public.schema_migrations(filename, checksum) values (%s, %s)",
                            (f.name, checksum(f)),
                        )
                print(f"APPLIED {f.name}")
            print(f"\n{len(pending)} migration(s) appliquée(s).")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERREUR migrations : {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

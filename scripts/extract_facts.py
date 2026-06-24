from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.services.ingestion_pipeline import IngestionPipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Extraction MemGraphRAG (entités/relations) sur les chunks d'un document.")
    parser.add_argument("--document-id", required=True, help="UUID du document zora à traiter.")
    parser.add_argument("--limit", type=int, default=0, help="Nombre max de chunks (0 = tous les non traités).")
    parser.add_argument("--detect-conflicts", action="store_true", help="Active la supersession temporelle.")
    args = parser.parse_args()
    configure_logging()

    pipeline = IngestionPipeline()
    if not pipeline.configured():
        print("ERREUR: LLM provider non configuré (.env).", file=sys.stderr)
        return 2

    # Resumable : on saute les chunks ayant déjà un passage (mem_passages.source_chunk_id).
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select c.id, c.content
            from zora.chunks c
            left join memgraph.mem_passages p on p.source_chunk_id = c.id
            where c.document_id = %s and p.id is null and length(trim(c.content)) > 0
            order by c.ordinal
            """,
            (args.document_id,),
        )
        rows = [(str(r["id"]), r["content"]) for r in cur.fetchall()]

    if args.limit:
        rows = rows[: args.limit]
    print(f"chunks à extraire: {len(rows)}", flush=True)

    tot_e = tot_f = tot_c = 0
    started = time.time()
    for i, (chunk_id, content) in enumerate(rows, 1):
        try:
            res = pipeline.extract_and_store(
                content,
                source_document_id=args.document_id,
                source_chunk_id=chunk_id,
                detect_conflicts=args.detect_conflicts,
            )
            tot_e += res["entities"]
            tot_f += res["facts"]
            tot_c += len(res["conflicts"])
            print(f"[{i}/{len(rows)}] chunk {chunk_id[:8]} -> {res['entities']} entités, {res['facts']} faits", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}/{len(rows)}] chunk {chunk_id[:8]} ÉCHEC: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    print(f"TERMINÉ: {tot_e} entités, {tot_f} faits, {tot_c} conflits en {time.time() - started:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

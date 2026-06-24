from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.services.embedding_service import EmbeddingError, EmbeddingService, to_pgvector  # noqa: E402


def count_remaining(cur) -> int:
    cur.execute("select count(*) c from zora.chunks where embedding is null and length(trim(content)) > 0")
    return cur.fetchone()["c"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill des embeddings manquants sur zora.chunks.")
    parser.add_argument("--db-batch", type=int, default=256, help="Chunks lus/écrits par tour.")
    parser.add_argument("--limit", type=int, default=0, help="Nombre max de chunks à traiter (0 = tous).")
    parser.add_argument("--max-retries", type=int, default=4)
    args = parser.parse_args()
    configure_logging()

    embedder = EmbeddingService()
    if not embedder.configured():
        print("ERREUR: embedding provider non configuré (.env).", file=sys.stderr)
        return 2

    processed = 0
    started = time.time()
    with get_connection() as conn:
        with conn.cursor() as cur:
            remaining = count_remaining(cur)
        print(f"chunks à vectoriser: {remaining}", flush=True)

        while True:
            if args.limit and processed >= args.limit:
                break
            take = args.db_batch
            if args.limit:
                take = min(take, args.limit - processed)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select id, content from zora.chunks
                    where embedding is null and length(trim(content)) > 0
                    order by created_at
                    limit %s
                    """,
                    (take,),
                )
                rows = cur.fetchall()
            if not rows:
                break

            texts = [r["content"] for r in rows]
            ids = [r["id"] for r in rows]

            vectors = None
            for attempt in range(1, args.max_retries + 1):
                try:
                    vectors = embedder.embed_texts(texts, input_type="passage")
                    break
                except EmbeddingError as exc:
                    wait = min(30, 2 ** attempt)
                    print(f"  embed échec (tentative {attempt}/{args.max_retries}): {exc} -> retry {wait}s", flush=True)
                    time.sleep(wait)
            if vectors is None:
                print("ARRÊT: embeddings indisponibles après retries (resumable, relancer plus tard).", file=sys.stderr)
                return 3

            with conn.cursor() as cur:
                cur.executemany(
                    "update zora.chunks set embedding = %s::vector where id = %s",
                    [(to_pgvector(v), cid) for v, cid in zip(vectors, ids)],
                )
            conn.commit()
            processed += len(rows)
            rate = processed / max(1e-6, time.time() - started)
            print(f"vectorisés: {processed} (+{len(rows)}) ~{rate:.1f}/s", flush=True)

    print(f"TERMINÉ: {processed} chunks vectorisés en {time.time() - started:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

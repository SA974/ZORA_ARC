from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


SOURCE_DB = "RAG_ARC"
TARGET_DB = "rag_arc"
MIGRATION_NAME = "rag_arc_public_to_arc_mem_v0_1"
NAMESPACE = uuid.UUID("a2de6a45-f8b8-4bb4-9f0c-5f2be5c1d9b9")


def stable_uuid(kind: str, legacy_id: int) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{SOURCE_DB}:{kind}:{legacy_id}")


def connect(db: str):
    return psycopg.connect(get_settings().postgres_dsn(database=db), row_factory=dict_row)


def database_exists(db: str) -> bool:
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn(database="postgres"), row_factory=dict_row) as conn:
        return bool(scalar(conn, "select exists(select 1 from pg_database where datname=%s)", (db,)))


def scalar(conn, sql: str, params: tuple[Any, ...] = ()) -> Any:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        return next(iter(row.values())) if isinstance(row, dict) else row[0]


def counts() -> dict[str, Any]:
    out: dict[str, Any] = {"source": {}, "target": {}}
    out["source"]["exists"] = database_exists(SOURCE_DB)
    if out["source"]["exists"]:
        with connect(SOURCE_DB) as conn:
            for name, sql in {
                "documents": "select count(*) from public.documents",
                "chunks": "select count(*) from public.chunks",
                "embeddings": "select count(*) from public.embeddings",
                "chunks_with_embeddings": """
                    select count(*)
                    from public.chunks c
                    where exists (select 1 from public.embeddings e where e.chunk_id=c.id)
                """,
            }.items():
                out["source"][name] = scalar(conn, sql)
    with connect(TARGET_DB) as conn:
        for name, sql in {
            "documents": "select count(*) from zora.documents where metadata->>'source_db' = %s",
            "chunks": "select count(*) from zora.chunks where metadata->>'source_db' = %s",
            "chunks_with_embeddings": """
                select count(*) from zora.chunks
                where metadata->>'source_db' = %s and embedding is not null
            """,
        }.items():
            out["target"][name] = scalar(conn, sql, (SOURCE_DB,))
        out["target"]["embedding_type"] = scalar(
            conn,
            """
            select format_type(a.atttypid, a.atttypmod)
            from pg_attribute a
            join pg_class c on c.oid=a.attrelid
            join pg_namespace n on n.oid=c.relnamespace
            where n.nspname='zora' and c.relname='chunks' and a.attname='embedding'
            """,
        )
    return out


def prepare_target(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("drop index if exists zora.idx_zora_chunks_embedding_hnsw")
        cur.execute("drop index if exists zora.idx_zora_chunks_embedding_ivfflat")
        cur.execute("alter table zora.chunks alter column embedding type vector(1024)")
        cur.execute(
            """
            create table if not exists zora.legacy_migration_audit (
              id uuid primary key default gen_random_uuid(),
              migration_name text not null,
              source_db text not null,
              target_db text not null,
              status text not null,
              counts jsonb not null default '{}',
              backup_path text,
              message text,
              created_at timestamptz not null default now()
            )
            """
        )
        cur.execute(
            """
            create table if not exists zora.legacy_id_map (
              source_db text not null,
              source_table text not null,
              legacy_id bigint not null,
              target_schema text not null,
              target_table text not null,
              target_id uuid not null,
              created_at timestamptz not null default now(),
              primary key(source_db, source_table, legacy_id)
            )
            """
        )
    conn.commit()


def migrate_documents(source, target, batch_size: int) -> int:
    total = 0
    last_id = 0
    while True:
        rows = source.execute(
            """
            select d.*, s.name as source_name, s.path as source_path, s.description as source_description
            from public.documents d
            left join public.sources s on s.id=d.source_id
            where d.id > %s
            order by d.id
            limit %s
            """,
            (last_id, batch_size),
        ).fetchall()
        if not rows:
            return total
        payload = []
        maps = []
        for row in rows:
            legacy_id = int(row["id"])
            target_id = stable_uuid("document", legacy_id)
            title = row["title"] or row["filename"]
            metadata = {
                "source_db": SOURCE_DB,
                "source_table": "public.documents",
                "legacy_id": legacy_id,
                "source_id": row["source_id"],
                "filename": row["filename"],
                "file_path": row["file_path"],
                "file_size_bytes": row["file_size_bytes"],
                "author": row["author"],
                "page_count": row["page_count"],
                "creation_date": str(row["creation_date"]) if row["creation_date"] else None,
                "domain": row["domain"],
                "category": row["category"],
                "tags": row["tags"],
                "status": row["status"],
                "status_message": row["status_message"],
                "processed_at": str(row["processed_at"]) if row["processed_at"] else None,
                "source_name": row["source_name"],
                "source_path": row["source_path"],
                "source_description": row["source_description"],
                "migration": MIGRATION_NAME,
            }
            payload.append(
                (
                    target_id,
                    title,
                    row["file_path"],
                    row["file_hash"],
                    json.dumps(metadata, ensure_ascii=False),
                    row["ingested_at"] or row["updated_at"],
                )
            )
            maps.append((SOURCE_DB, "public.documents", legacy_id, "zora", "documents", target_id))
            last_id = legacy_id
        with target.cursor() as cur:
            cur.executemany(
                """
                insert into zora.documents(id, title, source_uri, content_hash, metadata, created_at)
                values (%s, %s, %s, %s, %s::jsonb, coalesce(%s, now()))
                on conflict (id) do update set
                  title=excluded.title,
                  source_uri=excluded.source_uri,
                  content_hash=excluded.content_hash,
                  metadata=excluded.metadata
                """,
                payload,
            )
            cur.executemany(
                """
                insert into zora.legacy_id_map(source_db, source_table, legacy_id, target_schema, target_table, target_id)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (source_db, source_table, legacy_id) do update set target_id=excluded.target_id
                """,
                maps,
            )
        target.commit()
        total += len(rows)
        print(f"documents migrated: {total}", flush=True)


def migrate_chunks(source, target, batch_size: int) -> int:
    total = 0
    last_id = 0
    while True:
        rows = source.execute(
            """
            select
              c.id, c.document_id, c.chunk_index, c.chunk_hash, c.content, c.content_length,
              c.token_count, c.page_start, c.page_end, c.section_title,
              c.chunk_size_strategy, c.overlap_size, c.created_at,
              e.id as embedding_id, e.embedding::text as embedding_text, e.model_name,
              e.model_version, e.embedding_dimension, e.similarity_norm,
              e.created_at as embedding_created_at
            from public.chunks c
            left join lateral (
              select *
              from public.embeddings e
              where e.chunk_id=c.id
              order by e.id
              limit 1
            ) e on true
            where c.id > %s
            order by c.id
            limit %s
            """,
            (last_id, batch_size),
        ).fetchall()
        if not rows:
            return total
        payload = []
        maps = []
        for row in rows:
            legacy_id = int(row["id"])
            target_id = stable_uuid("chunk", legacy_id)
            target_document_id = stable_uuid("document", int(row["document_id"]))
            metadata = {
                "source_db": SOURCE_DB,
                "source_table": "public.chunks",
                "legacy_id": legacy_id,
                "legacy_document_id": row["document_id"],
                "chunk_hash": row["chunk_hash"],
                "content_length": row["content_length"],
                "token_count": row["token_count"],
                "page_start": row["page_start"],
                "page_end": row["page_end"],
                "section_title": row["section_title"],
                "chunk_size_strategy": row["chunk_size_strategy"],
                "overlap_size": row["overlap_size"],
                "embedding_id": row["embedding_id"],
                "embedding_model": row["model_name"],
                "embedding_model_version": row["model_version"],
                "embedding_dimension": row["embedding_dimension"],
                "similarity_norm": row["similarity_norm"],
                "embedding_created_at": str(row["embedding_created_at"]) if row["embedding_created_at"] else None,
                "migration": MIGRATION_NAME,
            }
            payload.append(
                (
                    target_id,
                    target_document_id,
                    row["chunk_index"],
                    row["content"],
                    row["embedding_text"],
                    json.dumps(metadata, ensure_ascii=False),
                    row["created_at"],
                )
            )
            maps.append((SOURCE_DB, "public.chunks", legacy_id, "zora", "chunks", target_id))
            last_id = legacy_id
        with target.cursor() as cur:
            cur.executemany(
                """
                insert into zora.chunks(id, document_id, ordinal, content, embedding, metadata, created_at)
                values (%s, %s, %s, %s, %s::vector, %s::jsonb, coalesce(%s, now()))
                on conflict (id) do update set
                  document_id=excluded.document_id,
                  ordinal=excluded.ordinal,
                  content=excluded.content,
                  embedding=excluded.embedding,
                  metadata=excluded.metadata
                """,
                payload,
            )
            cur.executemany(
                """
                insert into zora.legacy_id_map(source_db, source_table, legacy_id, target_schema, target_table, target_id)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (source_db, source_table, legacy_id) do update set target_id=excluded.target_id
                """,
                maps,
            )
        target.commit()
        total += len(rows)
        print(f"chunks migrated: {total}", flush=True)


def rebuild_indexes(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create index if not exists idx_zora_chunks_embedding_hnsw
            on zora.chunks using hnsw (embedding vector_cosine_ops)
            """
        )
    conn.commit()


def write_audit(
    status: str,
    backup_path: str | None,
    message: str | None = None,
    current_counts: dict[str, Any] | None = None,
) -> None:
    with connect(TARGET_DB) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into zora.legacy_migration_audit(migration_name, source_db, target_db, status, counts, backup_path, message)
                values (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    MIGRATION_NAME,
                    SOURCE_DB,
                    TARGET_DB,
                    status,
                    json.dumps(current_counts or {}, default=str),
                    backup_path,
                    message,
                ),
            )
        conn.commit()


def drop_source_database() -> None:
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn(database="postgres"), autocommit=True, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select pg_terminate_backend(pid)
                from pg_stat_activity
                where datname = %s and pid <> pg_backend_pid()
                """,
                (SOURCE_DB,),
            )
            cur.execute(f'drop database if exists "{SOURCE_DB}"')


def validate_or_raise() -> dict[str, Any]:
    current = counts()
    if not current["source"].get("exists"):
        raise RuntimeError(f"source database {SOURCE_DB} does not exist")
    expected_docs = current["source"]["documents"]
    expected_chunks = current["source"]["chunks"]
    expected_embeddings = current["source"]["chunks_with_embeddings"]
    got_docs = current["target"]["documents"]
    got_chunks = current["target"]["chunks"]
    got_embeddings = current["target"]["chunks_with_embeddings"]
    errors = []
    if got_docs != expected_docs:
        errors.append(f"documents mismatch: source={expected_docs}, target={got_docs}")
    if got_chunks != expected_chunks:
        errors.append(f"chunks mismatch: source={expected_chunks}, target={got_chunks}")
    if got_embeddings != expected_embeddings:
        errors.append(f"embeddings mismatch: source={expected_embeddings}, target={got_embeddings}")
    if current["target"]["embedding_type"] != "vector(1024)":
        errors.append(f"target embedding type is {current['target']['embedding_type']}, expected vector(1024)")
    if errors:
        raise RuntimeError("; ".join(errors))
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy RAG_ARC corpus into ARC-MEM rag_arc.")
    parser.add_argument("--execute", action="store_true", help="Run the migration. Without this flag, only print counts.")
    parser.add_argument("--drop-source", action="store_true", help="Drop RAG_ARC after a successful validation.")
    parser.add_argument("--backup-path", help="Backup dump path to record in audit log.")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    print(json.dumps({"preflight": counts()}, indent=2, ensure_ascii=False, default=str), flush=True)
    if args.drop_source and not args.execute:
        final_counts = validate_or_raise()
        drop_source_database()
        write_audit(
            "source_dropped",
            args.backup_path,
            "RAG_ARC dropped after successful migration validation",
            final_counts,
        )
        print(json.dumps({"status": "source_dropped", "source_db": SOURCE_DB}, indent=2, ensure_ascii=False))
        return 0

    if not args.execute:
        return 0

    started = time.time()
    try:
        with connect(SOURCE_DB) as source, connect(TARGET_DB) as target:
            prepare_target(target)
            migrate_documents(source, target, args.batch_size)
            migrate_chunks(source, target, args.batch_size)
            rebuild_indexes(target)
        final_counts = validate_or_raise()
        write_audit("completed", args.backup_path, f"duration_seconds={time.time() - started:.1f}", final_counts)
        print(json.dumps({"status": "completed", "counts": final_counts}, indent=2, ensure_ascii=False, default=str))
        if args.drop_source:
            drop_source_database()
            write_audit(
                "source_dropped",
                args.backup_path,
                "RAG_ARC dropped after successful migration validation",
                final_counts,
            )
            print(json.dumps({"status": "source_dropped", "source_db": SOURCE_DB}, indent=2, ensure_ascii=False))
    except Exception as exc:
        try:
            write_audit("failed", args.backup_path, f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path


def test_memgraph_schema_preserves_provenance():
    sql = Path("app/migrations/003_init_memgraph_schema.sql").read_text(encoding="utf-8")
    assert "source_document_id" in sql
    assert "source_chunk_id" in sql
    assert "provenance_text" in sql
    assert "mem_facts_has_provenance" in sql


def test_hindsight_schema_not_created():
    migrations = "\n".join(path.read_text(encoding="utf-8") for path in Path("app/migrations").glob("*.sql"))
    assert "create schema if not exists hindsight" not in migrations.lower()

"""Validation fonctionnelle des Lots 0-2 (Ollama / PostgreSQL / PDF / embeddings).

Sortie : une ligne PASS/FAIL par contrôle, code retour != 0 si au moins un FAIL.
N'écrit RIEN de durable en base (insert testé puis rollback).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.config import get_settings
from app.db import get_connection
from app.services.embedding_service import EmbeddingService, to_pgvector
from app.services.embedding_service_ollama import (
    EmbeddingError,
    EmbeddingServiceOllama,
    OllamaSettings,
)
from app.services.pdf_service import chunk_pages, sanitize_text

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, bool(cond), detail))


s = get_settings()
base = "http://localhost:11434"

# ---------- A. Ollama ----------
try:
    with httpx.Client(timeout=15) as c:
        tags = c.get(f"{base}/api/tags").json()
        models = [m["name"] for m in tags.get("models", [])]
        check("A1 Ollama /api/tags joignable", True, f"{len(models)} modèles")
        emb = c.post(f"{base}/api/embeddings",
                     json={"model": "nomic-embed-text", "prompt": "agronomie"}, timeout=30).json()
        check("A2 nomic-embed-text dim==768", len(emb.get("embedding", [])) == 768,
              f"dim={len(emb.get('embedding', []))}")
        gen = c.post(f"{base}/api/generate",
                     json={"model": "qwen:14b", "prompt": "Dis OK.", "stream": False}, timeout=60).json()
        check("A3 qwen:14b génère", bool(gen.get("response")), "")
except Exception as e:
    check("A1 Ollama joignable", False, f"{type(e).__name__}: {e}")

# A4 : modèle absent géré proprement (erreur explicite, pas de crash)
try:
    EmbeddingServiceOllama(OllamaSettings(base_url=base, embedding_model="modele-inexistant-xyz")).embed_texts(["x"])
    check("A4 modèle absent -> EmbeddingError", False, "aucune erreur levée")
except EmbeddingError as e:
    check("A4 modèle absent -> EmbeddingError", True, str(e)[:60])
except Exception as e:
    check("A4 modèle absent -> EmbeddingError", False, f"mauvaise exception {type(e).__name__}")

# ---------- B. PostgreSQL ----------
try:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select 1")
        check("B1 connexion PostgreSQL", cur.fetchone()["?column?"] == 1)

        cur.execute("select extname from pg_extension")
        ext = {r["extname"] for r in cur.fetchall()}
        check("B2 extensions vector+postgis", {"vector", "postgis"} <= ext, str(sorted(ext)))

        cur.execute("""select format_type(a.atttypid,a.atttypmod) t
                       from pg_attribute a join pg_class c on c.oid=a.attrelid
                       join pg_namespace n on n.oid=c.relnamespace
                       where a.attname='embedding' and c.relkind='r'
                         and n.nspname||'.'||c.relname = any(%s)""",
                    (["zora.chunks", "memgraph.mem_facts", "memgraph.mem_entities"],))
        dims = {r["t"] for r in cur.fetchall()}
        check("B3 colonnes vectorielles actives==768", dims == {"vector(768)"}, str(dims))

        cur.execute("""select count(*) n from information_schema.columns
                       where table_schema='zora' and table_name='chunks'
                         and column_name in ('content_chars','content_tokens_estimated')""")
        check("B4 colonnes content_length présentes", cur.fetchone()["n"] == 2)

        cur.execute("""select content_chars, content_tokens_estimated, char_length(content) cl
                       from zora.chunks where content_chars is not null limit 1""")
        r = cur.fetchone()
        check("B5 content_chars==char_length & tokens==chars/4",
              r["content_chars"] == r["cl"] and r["content_tokens_estimated"] == max(1, r["cl"] // 4),
              f"chars={r['content_chars']} tokens={r['content_tokens_estimated']}")

        # B6 requête de similarité vectorielle réelle (pgvector opérationnel)
        cur.execute("select embedding from zora.chunks where embedding is not null limit 1")
        vec = cur.fetchone()["embedding"]
        cur.execute("select id from zora.chunks order by embedding <=> %s::vector limit 3", (vec,))
        check("B6 requête KNN pgvector (<=>)", len(cur.fetchall()) == 3)

        # B7 écriture transactionnelle testée puis ROLLBACK (aucun résidu)
        with conn.transaction(force_rollback=True):
            cur.execute("insert into zora.documents(title, metadata) values ('VALIDATION_TMP','{}') returning id")
            doc_id = cur.fetchone()["id"]
            cur.execute("insert into zora.chunks(document_id, ordinal, content, embedding) "
                        "values (%s, 0, 'tmp', %s::vector)", (doc_id, to_pgvector([0.0] * 768)))
        cur.execute("select count(*) n from zora.documents where title='VALIDATION_TMP'")
        check("B7 insert transactionnel + rollback propre", cur.fetchone()["n"] == 0)
except Exception as e:
    check("B1 PostgreSQL", False, f"{type(e).__name__}: {e}")

# ---------- C. PDF / chunking / embeddings ----------
pages = ["Page une " + "alpha " * 300, "Page deux " + "beta\x00 " * 300, ""]
check("C1 sanitize_text retire les NUL", "\x00" not in sanitize_text(pages[1]))
chunks = chunk_pages([sanitize_text(p) for p in pages])
check("C2 chunking produit des chunks", len(chunks) > 0, f"{len(chunks)} chunks")
ok_inv = all(c.char_end > c.char_start and c.content for c in chunks) and \
         [c.ordinal for c in chunks] == list(range(len(chunks)))
check("C3 invariants chunk (ordinaux contigus, spans>0)", ok_inv)

try:
    ollama = EmbeddingServiceOllama()
    v = ollama.embed_texts([chunks[0].content], input_type="passage")[0]
    check("C4 embedding d'un chunk (ingestion) == 768", len(v) == 768, f"dim={len(v)}")
except Exception as e:
    check("C4 embedding chunk", False, f"{type(e).__name__}: {e}")

# C5 chemin RECHERCHE : EmbeddingService OpenAI-compat /v1/embeddings
try:
    q = EmbeddingService().embed_query("quelle est la culture du thé ?")
    check("C5 embed_query (recherche /v1) == 768", len(q) == 768, f"dim={len(q)}")
except Exception as e:
    check("C5 embed_query", False, f"{type(e).__name__}: {e}")

# ---------- Rapport ----------
print("\n=== VALIDATION LOTS 0-2 ===")
n_pass = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
print(f"\n{n_pass}/{len(results)} contrôles PASS")
sys.exit(0 if n_pass == len(results) else 1)

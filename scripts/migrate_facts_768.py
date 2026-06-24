"""Migration memgraph.mem_facts.embedding : vector(1024) NVIDIA -> vector(768) Ollama nomic.

Phase A : recalcule les 161 embeddings (texte = 'subject predicate object_value') en 768D.
Phase B : transaction atomique (drop vue+index, alter colonne, recree vue+index, update vecteurs).
Phase C : verification.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import get_connection
from app.services.embedding_service_ollama import EmbeddingServiceOllama
from app.services.embedding_service import to_pgvector

VIEW_DDL = """
create view memgraph.v_active_facts as
 SELECT id, subject, predicate, object_value, source_document_id, source_chunk_id,
        provenance_text, confidence, status, metadata, created_at, embedding,
        observed_at, valid_from, valid_to, salience, decay_rate, last_accessed_at,
        access_count, reinforced_count, superseded_by,
        memgraph.fact_salience_now(salience, decay_rate, COALESCE(last_accessed_at, observed_at)) AS salience_now
   FROM memgraph.mem_facts f
  WHERE superseded_by IS NULL AND (valid_to IS NULL OR valid_to > now())
        AND status <> 'inactive'::memgraph.memgraph_status;
"""
INDEX_DDL = "create index idx_mem_facts_embedding_hnsw on memgraph.mem_facts using hnsw (embedding vector_cosine_ops)"

emb = EmbeddingServiceOllama()
print("Embedder configured:", emb.configured(), "| model:", emb.settings.embedding_model, "| dim:", emb.settings.embedding_dim)

# --- Phase A : recompute en memoire ---
with get_connection() as conn, conn.cursor() as cur:
    cur.execute("select id, subject, predicate, object_value from memgraph.mem_facts order by created_at")
    facts = cur.fetchall()
print(f"Phase A : {len(facts)} faits a re-vectoriser")

new_vecs = {}
for f in facts:
    text = f"{f['subject']} {f['predicate']} {f['object_value']}"
    vec = emb.embed_texts([text], input_type="passage")[0]
    if len(vec) != 768:
        raise SystemExit(f"ABORT: dim {len(vec)} != 768 pour fait {f['id']}")
    new_vecs[f["id"]] = vec
print(f"Phase A OK : {len(new_vecs)} vecteurs 768D calcules")

# --- Phase B : migration transactionnelle ---
with get_connection() as conn:
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("drop view if exists memgraph.v_active_facts")
            cur.execute("drop index if exists memgraph.idx_mem_facts_embedding_hnsw")
            cur.execute("alter table memgraph.mem_facts alter column embedding type vector(768) using null::vector(768)")
            cur.execute(VIEW_DDL)
            cur.execute(INDEX_DDL)
            for fid, vec in new_vecs.items():
                cur.execute("update memgraph.mem_facts set embedding=%s::vector where id=%s", (to_pgvector(vec), fid))
print("Phase B OK : schema migre + vecteurs mis a jour (transaction commitee)")

# --- Phase C : verification ---
with get_connection() as conn, conn.cursor() as cur:
    cur.execute("select atttypmod from pg_attribute where attrelid='memgraph.mem_facts'::regclass and attname='embedding'")
    print("Phase C : nouvelle dim colonne =", cur.fetchone()[0])
    cur.execute("select count(*) total, count(embedding) with_emb, min(vector_dims(embedding)) dmin, max(vector_dims(embedding)) dmax from memgraph.mem_facts")
    print("Phase C : facts =", cur.fetchone())

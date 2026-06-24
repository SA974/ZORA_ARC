"""Migration memgraph.mem_entities.embedding : vector(1024) NVIDIA -> vector(768) Ollama nomic.

Aligne mem_entities sur mem_facts et zora.chunks (tous en 768D). Les embeddings 1024D
ne sont pas tronquables : ils sont RECALCULÉS depuis le texte de l'entité.

Phase A : recalcule les embeddings (texte = nom de l'entité) en 768D.
Phase B : transaction atomique -> backup table, alter colonne, index HNSW, update vecteurs.
Phase C : vérification.

Idempotent : si la colonne est déjà en 768, ne fait rien (sauf (re)créer l'index manquant).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection
from app.services.embedding_service import to_pgvector
from app.services.embedding_service_ollama import EmbeddingServiceOllama

INDEX_DDL = (
    "create index if not exists idx_mem_entities_embedding_hnsw "
    "on memgraph.mem_entities using hnsw (embedding vector_cosine_ops)"
)


def current_dim(cur) -> int | None:
    cur.execute(
        "select format_type(atttypid, atttypmod) t from pg_attribute "
        "where attrelid='memgraph.mem_entities'::regclass and attname='embedding'"
    )
    row = cur.fetchone()
    if not row:
        return None
    t = row["t"]  # ex: 'vector(1024)'
    return int(t[t.index("(") + 1 : t.index(")")]) if "(" in t else None


def main() -> int:
    emb = EmbeddingServiceOllama()
    print("Embedder configured:", emb.configured(),
          "| model:", emb.settings.embedding_model, "| dim:", emb.settings.embedding_dim)

    with get_connection() as conn, conn.cursor() as cur:
        dim = current_dim(cur)
        print("Dimension actuelle de mem_entities.embedding =", dim)
        if dim == 768:
            cur.execute(INDEX_DDL)
            conn.commit()
            print("Déjà en 768D. Index HNSW assuré. Rien d'autre à faire.")
            return 0

    # --- Phase A : recompute en mémoire (un seul appel -> connexion HTTP réutilisée) ---
    import time
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select id, name, entity_type from memgraph.mem_entities order by created_at")
        entities = cur.fetchall()
    print(f"Phase A : {len(entities)} entités à re-vectoriser", flush=True)

    new_vecs: dict[str, list[float]] = {}
    t0 = time.time()
    batch = 64
    for start in range(0, len(entities), batch):
        window = entities[start : start + batch]
        vecs = emb.embed_texts([e["name"] for e in window], input_type="passage")
        for e, vec in zip(window, vecs):
            if len(vec) != 768:
                raise SystemExit(f"ABORT: dim {len(vec)} != 768 pour entité {e['id']}")
            new_vecs[e["id"]] = vec
        print(f"  ... {len(new_vecs)}/{len(entities)} ({time.time() - t0:.0f}s)", flush=True)
    print(f"Phase A OK : {len(new_vecs)} vecteurs 768D calculés", flush=True)

    # --- Phase B : migration transactionnelle ---
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "create table if not exists memgraph.mem_entities_backup_1024 as "
                    "table memgraph.mem_entities"
                )
                cur.execute("drop index if exists memgraph.idx_mem_entities_embedding_hnsw")
                cur.execute(
                    "alter table memgraph.mem_entities "
                    "alter column embedding type vector(768) using null::vector(768)"
                )
                cur.execute(INDEX_DDL)
                for eid, vec in new_vecs.items():
                    cur.execute(
                        "update memgraph.mem_entities set embedding=%s::vector where id=%s",
                        (to_pgvector(vec), eid),
                    )
    print("Phase B OK : schéma migré + vecteurs mis à jour (transaction commitée)")

    # --- Phase C : vérification ---
    with get_connection() as conn, conn.cursor() as cur:
        print("Phase C : nouvelle dim colonne =", current_dim(cur))
        cur.execute(
            "select count(*) total, count(embedding) with_emb, "
            "min(vector_dims(embedding)) dmin, max(vector_dims(embedding)) dmax "
            "from memgraph.mem_entities"
        )
        print("Phase C : entities =", dict(cur.fetchone()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

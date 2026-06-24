from __future__ import annotations

import logging
from typing import Any

from app.db import get_connection
from app.services.embedding_service import EmbeddingService, to_pgvector

logger = logging.getLogger(__name__)

# --- Choix d'ingénierie (H-MEM ne donne aucune équation, cf. migration 006) -------------------
# Feedback multiplicatif appliqué à la salience décroissante courante :
#   approbation -> renforce, réfutation -> atténue, neutre -> laisse la courbe d'oubli agir.
FEEDBACK_MULTIPLIERS = {"approval": 1.3, "neutral": 1.0, "rebuttal": 0.5}
# Seuil de similarité cosinus au-delà duquel deux faits (même sujet/prédicat) sont jugés
# sémantiquement liés et candidats à un conflit temporel.
CONFLICT_SIM_THRESHOLD = 0.80


class TemporalService:
    def __init__(self) -> None:
        self.embedder = EmbeddingService()

    # --- Création de fait avec embedding + champs temporels ----------------------------------
    def add_fact(
        self,
        subject: str,
        predicate: str,
        object_value: str,
        provenance_text: str,
        source_document_id: str | None = None,
        source_chunk_id: str | None = None,
        confidence: float = 0.5,
        valid_from: str | None = None,
        valid_to: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        vec = None
        if self.embedder.configured():
            try:
                vec = self.embedder.embed_texts([f"{subject} {predicate} {object_value}"], "passage")[0]
            except Exception as exc:  # noqa: BLE001
                logger.warning("fait créé sans embedding: %s", type(exc).__name__)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into memgraph.mem_facts(
                  subject, predicate, object_value, provenance_text,
                  source_document_id, source_chunk_id, confidence, status,
                  embedding, observed_at, valid_from, valid_to
                )
                values (%s,%s,%s,%s,%s,%s,%s,'pending',
                        %s::vector, coalesce(%s::timestamptz, now()), %s::timestamptz, %s::timestamptz)
                returning id, subject, predicate, object_value, status, observed_at, valid_from, valid_to, salience
                """,
                (
                    subject, predicate, object_value, provenance_text,
                    source_document_id, source_chunk_id, confidence,
                    to_pgvector(vec) if vec is not None else None,
                    observed_at, valid_from, valid_to,
                ),
            )
            row = dict(cur.fetchone() or {})
            conn.commit()
            return row

    # --- Feedback (renforcement / oubli) -----------------------------------------------------
    def record_feedback(self, fact_id: str, signal: str, source: str = "user", note: str | None = None) -> dict[str, Any]:
        if signal not in FEEDBACK_MULTIPLIERS:
            raise ValueError(f"signal invalide: {signal!r} (attendu {tuple(FEEDBACK_MULTIPLIERS)})")
        mult = FEEDBACK_MULTIPLIERS[signal]
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select salience, decay_rate, last_accessed_at, observed_at,
                       memgraph.fact_salience_now(salience, decay_rate,
                         coalesce(last_accessed_at, observed_at)) as salience_now
                from memgraph.mem_facts where id = %s for update
                """,
                (fact_id,),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"fact introuvable: {fact_id}")
            before = float(row["salience_now"])
            if signal == "neutral":
                # On laisse la courbe d'oubli agir : aucune modif de salience/horloge.
                after = before
            else:
                after = max(0.0, min(1.0, before * mult))
                cur.execute(
                    """
                    update memgraph.mem_facts
                    set salience = %s,
                        last_accessed_at = now(),
                        reinforced_count = reinforced_count + case when %s = 'approval' then 1 else 0 end
                    where id = %s
                    """,
                    (after, signal, fact_id),
                )
            cur.execute(
                """
                insert into memgraph.mem_feedback(fact_id, signal, multiplier, salience_before, salience_after, source, note)
                values (%s,%s,%s,%s,%s,%s,%s)
                returning id
                """,
                (fact_id, signal, mult, round(before, 4), round(after, 4), source, note),
            )
            feedback_id = cur.fetchone()["id"]
            conn.commit()
        return {"ok": True, "fact_id": fact_id, "signal": signal, "salience_before": round(before, 4),
                "salience_after": round(after, 4), "feedback_id": str(feedback_id)}

    # --- Détection de conflit temporel -------------------------------------------------------
    def detect_temporal_conflict(self, fact_id: str) -> dict[str, Any]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select id, subject, predicate, object_value, embedding, valid_from, observed_at from memgraph.mem_facts where id = %s",
                (fact_id,),
            )
            f = cur.fetchone()
            if not f:
                raise KeyError(f"fact introuvable: {fact_id}")

            # Candidats : même sujet+prédicat, objet différent, non supplantés.
            has_emb = f["embedding"] is not None
            if has_emb:
                cur.execute(
                    """
                    select id, object_value, valid_from, observed_at,
                           (embedding <=> %s) as distance
                    from memgraph.mem_facts
                    where id <> %s and superseded_by is null
                      and lower(subject) = lower(%s) and lower(predicate) = lower(%s)
                      and lower(object_value) <> lower(%s) and embedding is not null
                    order by distance asc limit 10
                    """,
                    (f["embedding"], f["id"], f["subject"], f["predicate"], f["object_value"]),
                )
            else:
                cur.execute(
                    """
                    select id, object_value, valid_from, observed_at, null::float8 as distance
                    from memgraph.mem_facts
                    where id <> %s and superseded_by is null
                      and lower(subject) = lower(%s) and lower(predicate) = lower(%s)
                      and lower(object_value) <> lower(%s)
                    limit 10
                    """,
                    (f["id"], f["subject"], f["predicate"], f["object_value"]),
                )
            candidates = cur.fetchall()

            conflicts = []
            for c in candidates:
                sim = None if c["distance"] is None else round(1.0 - float(c["distance"]), 4)
                if sim is not None and sim < CONFLICT_SIM_THRESHOLD:
                    continue
                # Ordonnancement temporel : le plus récent (valid_from/observed_at) supplante l'ancien.
                t_new = f["valid_from"] or f["observed_at"]
                t_old = c["valid_from"] or c["observed_at"]
                if t_new and t_old and t_new >= t_old:
                    newer, older = f["id"], c["id"]
                else:
                    newer, older = c["id"], f["id"]
                cur.execute(
                    """
                    insert into memgraph.mem_conflicts(fact_id, conflicting_fact_id, conflict_type, status, similarity, detected_via)
                    values (%s,%s,'temporal','pending',%s,%s)
                    returning id
                    """,
                    (f["id"], c["id"], sim, "embedding" if has_emb else "lexical"),
                )
                conflict_id = cur.fetchone()["id"]
                # Supersession : l'ancien cède sa validité au nouveau.
                cur.execute(
                    """
                    update memgraph.mem_facts
                    set superseded_by = %s,
                        valid_to = coalesce(valid_to, (select coalesce(valid_from, observed_at) from memgraph.mem_facts where id = %s)),
                        status = 'inactive'
                    where id = %s
                    """,
                    (newer, newer, older),
                )
                conflicts.append({"conflict_id": str(conflict_id), "with": str(c["id"]),
                                  "similarity": sim, "superseded": str(older), "kept": str(newer)})
            conn.commit()
        return {"ok": True, "fact_id": fact_id, "conflicts": conflicts, "detected_via": "embedding" if has_emb else "lexical"}

    # --- Récupération de faits actifs (sémantique + salience), repli lexical -----------------
    def active_facts_for_query(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        qvec = self.embedder.try_embed_query(query)
        cols = "id, subject, predicate, object_value, provenance_text, confidence, status, observed_at, valid_from, valid_to, salience_now"
        try:
            with get_connection() as conn, conn.cursor() as cur:
                if qvec is not None:
                    literal = to_pgvector(qvec)
                    cur.execute(
                        f"""
                        select {cols}, round((1 - (embedding <=> %s::vector))::numeric, 4) as similarity,
                               round((salience_now * (1 - (embedding <=> %s::vector)))::numeric, 4) as combined_score
                        from memgraph.v_active_facts
                        where embedding is not null
                        order by salience_now * (1 - (embedding <=> %s::vector)) desc
                        limit %s
                        """,
                        (literal, literal, literal, limit),
                    )
                    rows = [dict(r) for r in cur.fetchall()]
                    if rows:
                        for r in rows:
                            r["retrieval_mode"] = "semantic_temporal"
                        return rows
                # Repli lexical (pas d'embedding requête, ou aucun fait vectorisé)
                like = f"%{query}%"
                cur.execute(
                    f"""
                    select {cols}
                    from memgraph.v_active_facts
                    where subject ilike %s or predicate ilike %s or object_value ilike %s or provenance_text ilike %s
                    order by salience_now desc, observed_at desc
                    limit %s
                    """,
                    (like, like, like, like, limit),
                )
                rows = [dict(r) for r in cur.fetchall()]
                for r in rows:
                    r["retrieval_mode"] = "lexical_temporal"
                return rows
        except Exception as exc:  # noqa: BLE001
            return [{"warning": f"temporal fact retrieval unavailable: {exc}"}]

    def touch_access(self, fact_ids: list[str]) -> None:
        """Incrémente le compteur d'accès (signal d'usage) SANS réinitialiser l'horloge de décroissance."""
        if not fact_ids:
            return
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "update memgraph.mem_facts set access_count = access_count + 1 where id = any(%s::uuid[])",
                    (fact_ids,),
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("touch_access ignoré: %s", exc)

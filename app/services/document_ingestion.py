from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from app.db import get_connection
from app.services.embedding_service import EmbeddingError, EmbeddingService, to_pgvector
from app.services.embedding_service_ollama import EmbeddingServiceOllama
from app.services.pdf_service import chunk_pages, compute_file_hash, extract_pdf_pages

logger = logging.getLogger(__name__)


def get_embedder():
    """Factory : crée le bon embedder selon EMBEDDING_PROVIDER (nvidia|ollama)."""
    provider = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return EmbeddingServiceOllama()
    else:
        return EmbeddingService()

# Dossiers ignorés lors d'un parcours récursif (logiciels, archives, artefacts).
DEFAULT_EXCLUDES = {
    "ACROBAT", "ACROBAT5", "READER", "PLUG_INS", "PLUGINS", "WEBBUY",
    "TOS_MDM", "TALEND", "ORG.TALEND", "_FILES", "TOC_DATA", "META-INF",
    "__MACOSX", "NODE_MODULES", ".GIT", "CACHE", "TEMP", "TMP",
    "ARCHIVES", "_ERREURS", "VRAC",
}

# Mapping mot-clé de chemin -> domaine (repris de l'ancien pipeline, source unique de vérité).
DEFAULT_DOMAIN_MAP = {
    "AGRICULTURE": "agronomie", "AGROFORESTERIE": "agronomie", "FORESTERIE": "agronomie",
    "ECOSYSTEME": "agronomie", "BIOLOGIE": "agronomie", "BOTANIQUE": "agronomie",
    "BIODIVERSITE": "agronomie", "ECOLOGIE": "ecologie",
    "THE": "the", "CAMELLIA": "the",
    "GEOGRAPHIE_SANTE": "geographie_sante", "GEOSANTE": "geographie_sante", "GEOSOCIALE": "geographie_sante",
    "SIG": "geomatique", "CARTOGRAPHIE": "geomatique", "TELEDETECTION": "geomatique", "HYDROLOGIE": "geomatique",
    "GEOGRAPHIE": "geographie", "ANTHROPOLOGIE": "anthropologie", "ETHNOLOGIE": "anthropologie",
    "ECONOMIE": "economie", "SOCIOLOGIE": "sociologie", "HISTOIRE": "histoire",
    "PHILOSOPHIE": "philosophie", "POLITIQUE": "politique", "RELIGION": "religions",
    "IOT_IA_AGRONOMIQUE": "iot_agronomique",
}


def resolve_domain(path: str | Path, fallback: str = "bibliotheque", domain_map: dict[str, str] | None = None) -> str:
    mapping = domain_map or DEFAULT_DOMAIN_MAP
    upper = str(path).upper()
    for keyword, domain in mapping.items():
        if keyword in upper:
            return domain
    return fallback


def _embed_with_retry(
    embedder: EmbeddingService, texts: list[str], *, attempts: int = 3, base_delay: float = 2.0,
    post_embed_delay: float = 0.0
) -> list[list[float]]:
    """Vectorise avec relance exponentielle (l'EmbeddingService gère déjà le batching/la dimension).

    post_embed_delay : délai après chaque appel API (pour respecter rate limit des free endpoints).
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            result = embedder.embed_texts(texts, input_type="passage")
            if post_embed_delay > 0:
                time.sleep(post_embed_delay)
            return result
        except EmbeddingError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning("embeddings échoués (tentative %d/%d), retry dans %.0fs: %s",
                               attempt + 1, attempts, delay, exc)
                time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _already_ingested(file_hash: str) -> str | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select id from zora.documents where content_hash = %s", (file_hash,))
        row = cur.fetchone()
        return str(row["id"]) if row else None


def _extract_chunks_to_memgraph(
    chunk_pairs: list[tuple[Any, str]], document_id: str, *, detect_conflicts: bool = False
) -> dict[str, Any]:
    """Lance l'extraction MemGraphRAG (entités/faits/passages) chunk par chunk.

    Isolation stricte : chaque chunk est traité indépendamment ; un échec d'extraction
    (LLM, parsing) est journalisé et n'interrompt ni les autres chunks ni l'ingestion.
    """
    from app.services.ingestion_pipeline import IngestionPipeline

    pipeline = IngestionPipeline()
    if not pipeline.configured():
        return {"status": "skipped_llm_not_configured", "entities": 0, "facts": 0, "conflicts": 0}

    entities = facts = conflicts = errors = 0
    for chunk, chunk_id in chunk_pairs:
        try:
            res = pipeline.extract_and_store(
                chunk.content, source_document_id=document_id, source_chunk_id=chunk_id,
                detect_conflicts=detect_conflicts,
            )
            entities += res["entities"]
            facts += res["facts"]
            conflicts += len(res["conflicts"])
        except Exception as exc:  # noqa: BLE001 - isolation par chunk
            errors += 1
            logger.warning("extraction chunk %s ignorée: %s", chunk_id, type(exc).__name__)
    return {"status": "done", "entities": entities, "facts": facts,
            "conflicts": conflicts, "errors": errors}


def ingest_pdf_file(
    path: str | Path,
    domain: str = "bibliotheque",
    *,
    dry_run: bool = False,
    max_pages: int = 0,
    embedder: EmbeddingService | None = None,
    post_embed_delay: float = 0.0,
    extract: bool = False,
    detect_conflicts: bool = False,
) -> dict[str, Any]:
    """Ingère UN PDF dans `zora` (base unique), de façon atomique et idempotente.

    Robustesse :
    - déduplication par `content_hash = SHA256(fichier)` (skip si déjà présent) ;
    - une seule transaction par document : en cas d'échec, rollback total -> aucune ligne
      orpheline et fichier reprenable au prochain passage ;
    - texte assaini (NUL, césures) et métadonnées de page conservées par chunk.
    """
    p = Path(path)
    if not p.exists():
        return {"ok": False, "status": "failed", "error": f"PDF introuvable: {p}"}
    if p.suffix.lower() != ".pdf":
        return {"ok": False, "status": "failed", "error": f"Le fichier n'est pas un PDF: {p}"}

    file_hash = compute_file_hash(p)
    file_size = p.stat().st_size

    existing = _already_ingested(file_hash)
    if existing:
        return {"ok": True, "status": "skipped", "document_id": existing,
                "file_hash": file_hash, "reason": "already_ingested"}

    enable_ocr = os.getenv("ENABLE_OCR", "0").lower() in ("1", "true", "yes")
    try:
        pages, page_count = extract_pdf_pages(p, enable_ocr=enable_ocr)
    except Exception as exc:  # noqa: BLE001 - PDF chiffré/corrompu/illisible : skip propre, pas un échec pipeline
        return {"ok": False, "status": "skipped_unreadable", "file_hash": file_hash,
                "error": f"PDF illisible: {type(exc).__name__}: {exc}"}
    if max_pages and page_count > max_pages:
        return {"ok": False, "status": "skipped_oversize_pages", "file_hash": file_hash, "pages": page_count,
                "error": f"document trop volumineux ({page_count} pages > {max_pages})"}

    chunks = chunk_pages(pages)
    if not chunks:
        return {"ok": False, "status": "skipped_empty", "file_hash": file_hash, "pages": page_count,
                "error": "aucun texte exploitable (PDF scanné/vide ? -> OCR requis)"}

    embedder = embedder or get_embedder()
    if not embedder.configured():
        return {"ok": False, "status": "failed", "file_hash": file_hash,
                "error": "fournisseur d'embeddings non configuré (model/base_url/api_key)"}

    model = embedder.settings.embedding_model
    if dry_run:
        return {"ok": True, "status": "dry_run", "file_hash": file_hash, "pages": page_count,
                "chunks": len(chunks), "embedding_model": model,
                "embedding_dim": embedder.settings.embedding_dim, "domain": domain}

    embeddings = _embed_with_retry(embedder, [c.content for c in chunks], post_embed_delay=post_embed_delay)
    ingested_at = datetime.now(timezone.utc).isoformat()
    doc_meta = {
        "filename": p.name, "source_path": str(p), "domain": domain,
        "page_count": page_count, "file_size_bytes": file_size,
        "ingested_at": ingested_at, "embedding_model": model, "source": "bridge-pdf",
    }

    chunk_pairs: list[tuple[Any, str]] = []  # (chunk, chunk_id) pour l'extraction optionnelle
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into zora.documents(title, source_uri, content_hash, metadata)
                    values (%s, %s, %s, %s::jsonb)
                    returning id
                    """,
                    (p.name, str(p), file_hash, Jsonb(doc_meta)),
                )
                document_id = cur.fetchone()["id"]
                for chunk, vector in zip(chunks, embeddings):
                    chunk_meta = {
                        "page_start": chunk.page_start, "page_end": chunk.page_end,
                        "char_start": chunk.char_start, "char_end": chunk.char_end,
                        "token_count": chunk.token_count, "embedding_model": model,
                    }
                    cur.execute(
                        """
                        insert into zora.chunks(document_id, ordinal, content, embedding, metadata)
                        values (%s, %s, %s, %s::vector, %s::jsonb)
                        on conflict (document_id, ordinal) do nothing
                        returning id
                        """,
                        (document_id, chunk.ordinal, chunk.content, to_pgvector(vector), Jsonb(chunk_meta)),
                    )
                    if extract:
                        row = cur.fetchone()
                        if row:
                            chunk_pairs.append((chunk, str(row["id"])))

    result = {"ok": True, "status": "ingested", "document_id": str(document_id), "file_hash": file_hash,
              "pages": page_count, "chunks": len(chunks), "embeddings": len(embeddings),
              "embedding_model": model, "domain": domain}

    # Extraction MemGraphRAG APRÈS le commit du stockage : un échec d'extraction ne fait
    # jamais perdre les chunks déjà stockés (les passages/faits sont ajoutés en plus).
    if extract:
        result["memgraph"] = _extract_chunks_to_memgraph(
            chunk_pairs, str(document_id), detect_conflicts=detect_conflicts
        )
    return result


def _walk_pdfs(root: Path, excludes: set[str], max_file_mb: int) -> tuple[list[Path], int]:
    """Liste les PDF accessibles, en élaguant les dossiers exclus et les fichiers trop gros."""
    pdfs: list[Path] = []
    oversize = 0
    max_bytes = max_file_mb * 1024 * 1024 if max_file_mb else 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d.upper() not in excludes]
        for name in filenames:
            if not name.lower().endswith(".pdf"):
                continue
            fp = Path(dirpath) / name
            try:
                if max_bytes and fp.stat().st_size > max_bytes:
                    oversize += 1
                    continue
                if not os.access(fp, os.R_OK):
                    continue
            except OSError:
                continue
            pdfs.append(fp)
    return pdfs, oversize


def ingest_folder(
    root: str | Path,
    *,
    fallback_domain: str = "bibliotheque",
    domain_map: dict[str, str] | None = None,
    excludes: set[str] | None = None,
    max_file_mb: int = 100,
    max_pages: int = 1500,
    limit: int = 0,
    dry_run: bool = False,
    report_path: str | Path | None = None,
    post_embed_delay: float = 0.0,
    extract: bool = False,
    detect_conflicts: bool = False,
) -> dict[str, Any]:
    """Ingère récursivement un dossier de PDF dans `zora`. Erreurs isolées par fichier.

    Si `extract`, chaque document alimente aussi MemGraphRAG (entités/faits/passages) via le LLM.
    """
    root = Path(root)
    excludes = {e.upper() for e in (excludes or DEFAULT_EXCLUDES)}
    embedder = get_embedder()

    # Preflight provider : on échoue VITE et clairement si l'embedder ne répond pas
    # ou renvoie une mauvaise dimension, plutôt qu'au 1er PDF après avoir scanné le lot.
    if not dry_run:
        from app.services.provider_health import preflight_embedder

        health = preflight_embedder(embedder)
        if not health["ok"]:
            logger.error("Preflight embedder échoué: %s", health.get("error"))
            return {
                "root": str(root), "dry_run": dry_run, "status": "provider_unhealthy",
                "ok": False, "error": health.get("error"), "provider_health": health,
                "total_found": 0, "ingested": 0, "skipped": 0, "failed": 0, "details": [],
            }
        # Si extraction demandée, le LLM doit répondre lui aussi (sinon échec rapide).
        if extract:
            from app.services.ingestion_pipeline import IngestionPipeline

            if not IngestionPipeline().configured():
                logger.error("Extraction demandée mais LLM non configuré")
                return {
                    "root": str(root), "dry_run": dry_run, "status": "llm_unhealthy",
                    "ok": False, "error": "extraction demandée mais LLM (extraction_model) non configuré",
                    "total_found": 0, "ingested": 0, "skipped": 0, "failed": 0, "details": [],
                }

    pdfs, oversize = _walk_pdfs(root, excludes, max_file_mb)
    if limit:
        pdfs = pdfs[:limit]

    summary: dict[str, Any] = {
        "root": str(root), "dry_run": dry_run, "started_at": datetime.now(timezone.utc).isoformat(),
        "total_found": len(pdfs), "skipped_oversize": oversize,
        "ingested": 0, "skipped": 0, "failed": 0, "dry_run_count": 0,
        "total_chunks": 0, "total_entities": 0, "total_facts": 0, "extract": extract, "details": [],
    }

    for index, fp in enumerate(pdfs, 1):
        domain = resolve_domain(fp, fallback_domain, domain_map)
        try:
            result = ingest_pdf_file(
                fp, domain, dry_run=dry_run, max_pages=max_pages, embedder=embedder,
                post_embed_delay=post_embed_delay, extract=extract, detect_conflicts=detect_conflicts,
            )
        except Exception as exc:  # noqa: BLE001 - isolation stricte par fichier
            result = {"ok": False, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}

        status = result.get("status", "failed")
        if status == "dry_run":
            summary["dry_run_count"] += 1
        else:
            summary[status] = summary.get(status, 0) + 1
        summary["total_chunks"] += int(result.get("chunks") or 0)
        mg = result.get("memgraph") or {}
        summary["total_entities"] += int(mg.get("entities") or 0)
        summary["total_facts"] += int(mg.get("facts") or 0)
        summary["details"].append({"file": str(fp), "domain": domain,
                                   **{k: v for k, v in result.items() if k != "ok"}})
        logger.info("[%d/%d] %s -> %s", index, len(pdfs), fp.name, status)

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    if report_path:
        Path(report_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Rapport écrit: %s", report_path)
    return summary

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Seuil (caractères) en dessous duquel une page est considérée "sans texte" (scannée).
OCR_MIN_CHARS = 10


@dataclass
class PageChunk:
    """Chunk page-aware : on conserve la (les) page(s) d'origine et la position caractère."""

    ordinal: int
    content: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    token_count: int


def compute_file_hash(path: str | Path, block_size: int = 65536) -> str:
    """SHA256 des OCTETS du fichier.

    On hashe le fichier (et non le texte extrait) pour aligner la déduplication sur
    `zora.documents.content_hash`, qui contient déjà le file_hash des documents migrés.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")  # césure de fin de ligne : "agri-\nculture" -> "agriculture"
_MULTISPACE = re.compile(r"[ \t]{2,}")
_MULTINEWLINE = re.compile(r"\n{3,}")


def sanitize_text(text: str) -> str:
    """Assainit le texte extrait d'un PDF.

    - supprime les NUL (\\x00) qui font échouer l'INSERT TEXT côté PostgreSQL ;
    - recolle les mots coupés par une césure de fin de ligne ;
    - normalise les espaces/sauts de ligne multiples.
    """
    if not text:
        return ""
    text = text.replace("\x00", "")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _MULTISPACE.sub(" ", text)
    text = _MULTINEWLINE.sub("\n\n", text)
    return text.strip()


@lru_cache(maxsize=1)
def _ocr_engine():
    """Charge PaddleOCR à la demande (lazy, mis en cache). Lève si indisponible."""
    from paddleocr import PaddleOCR  # import lourd : seulement si OCR demandé

    return PaddleOCR(use_angle_cls=True, lang="fr", show_log=False)


def _ocr_page(page) -> str:
    """OCR d'une page rendue en image. Renvoie "" en cas d'échec (jamais d'exception)."""
    try:
        import numpy as np

        pix = page.get_pixmap(dpi=200)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        result = _ocr_engine().ocr(img, cls=True)
        lines = []
        for block in result or []:
            for entry in block or []:
                if entry and len(entry) >= 2 and entry[1]:
                    lines.append(str(entry[1][0]))
        return sanitize_text("\n".join(lines))
    except Exception as exc:  # noqa: BLE001 - OCR best-effort, ne doit jamais casser l'ingestion
        logger.warning("OCR indisponible/échoué (%s) : page laissée vide", type(exc).__name__)
        return ""


def extract_pdf_pages(path: str | Path, *, enable_ocr: bool = False) -> tuple[list[str], int]:
    """Extrait le texte page par page (assaini). Renvoie (pages, nombre_de_pages).

    Si `enable_ocr` et qu'une page n'a (quasi) pas de texte extractible (PDF scanné),
    on tente un OCR best-effort sur le rendu image de la page.
    """
    doc = fitz.open(str(path))
    try:
        pages: list[str] = []
        for page in doc:
            text = sanitize_text(page.get_text())
            if enable_ocr and len(text) < OCR_MIN_CHARS:
                ocr_text = _ocr_page(page)
                if ocr_text:
                    text = ocr_text
            pages.append(text)
        return pages, doc.page_count
    finally:
        doc.close()


def _pages_for_span(page_bounds: list[tuple[int, int, int]], start: int, end: int) -> tuple[int, int]:
    """Détermine la première et la dernière page chevauchées par l'intervalle [start, end)."""
    page_start: int | None = None
    page_end: int | None = None
    for page_no, s, e in page_bounds:
        if e <= start:
            continue
        if s >= end:
            break
        if page_start is None:
            page_start = page_no
        page_end = page_no
    if page_start is None:
        last = page_bounds[-1][0] if page_bounds else 1
        return last, last
    return page_start, page_end  # type: ignore[return-value]


def chunk_pages(pages: list[str], size: int = 1200, overlap: int = 120) -> list[PageChunk]:
    """Découpe le texte (concaténé) en chunks page-aware.

    `size`/`overlap` en caractères (cohérent avec `app/api/ingest.py:chunk_text`).
    Garde-fou anti-boucle : l'overlap est borné strictement sous la taille.
    """
    if size <= 0:
        return []
    if overlap >= size:
        overlap = size // 4

    parts: list[str] = []
    page_bounds: list[tuple[int, int, int]] = []  # (n° page 1-based, offset début, offset fin)
    cursor = 0
    for i, page_text in enumerate(pages):
        if i > 0:
            parts.append("\n")
            cursor += 1
        start = cursor
        parts.append(page_text)
        cursor += len(page_text)
        page_bounds.append((i + 1, start, cursor))
    full = "".join(parts)
    total = len(full)

    chunks: list[PageChunk] = []
    start = 0
    ordinal = 0
    while start < total:
        end = min(total, start + size)
        content = full[start:end].strip()
        if content:
            page_start, page_end = _pages_for_span(page_bounds, start, end)
            chunks.append(
                PageChunk(
                    ordinal=ordinal,
                    content=content,
                    page_start=page_start,
                    page_end=page_end,
                    char_start=start,
                    char_end=end,
                    token_count=max(1, len(content) // 4),
                )
            )
            ordinal += 1
        if end == total:
            break
        start = max(end - overlap, start + 1)
    return chunks

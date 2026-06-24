"""Chunking page-aware des PDF (façade -> app.services.pdf_service)."""
from app.services.pdf_service import (  # noqa: F401
    OCR_MIN_CHARS,
    PageChunk,
    chunk_pages,
    extract_pdf_pages,
    sanitize_text,
)

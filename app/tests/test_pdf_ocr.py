"""Tests du hook OCR optionnel : désactivé = comportement inchangé, échec OCR = dégradation propre."""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.services import pdf_service
from app.services.pdf_service import extract_pdf_pages


@pytest.fixture
def text_pdf(tmp_path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Bonjour agronomie tropicale et theiculture.")
    p = tmp_path / "texte.pdf"
    doc.save(str(p))
    doc.close()
    return p


def test_ocr_disabled_returns_text(text_pdf):
    pages, n = extract_pdf_pages(text_pdf, enable_ocr=False)
    assert n == 1 and "agronomie" in pages[0]


def test_ocr_enabled_does_not_trigger_when_text_present(text_pdf, monkeypatch):
    # La page a du texte -> l'OCR ne doit PAS être appelé même si activé.
    called = {"n": 0}
    monkeypatch.setattr(pdf_service, "_ocr_page", lambda page: called.__setitem__("n", called["n"] + 1) or "")
    pages, _ = extract_pdf_pages(text_pdf, enable_ocr=True)
    assert "agronomie" in pages[0] and called["n"] == 0


def test_empty_page_with_ocr_unavailable_degrades_gracefully(tmp_path, monkeypatch):
    # Page vide + OCR activé mais moteur indisponible -> page "" sans exception.
    doc = fitz.open()
    doc.new_page()  # page blanche, aucun texte
    p = tmp_path / "vide.pdf"
    doc.save(str(p))
    doc.close()

    def boom():
        raise RuntimeError("paddleocr absent")

    monkeypatch.setattr(pdf_service, "_ocr_engine", boom)
    pages, n = extract_pdf_pages(p, enable_ocr=True)
    assert n == 1 and pages[0] == ""  # dégradation propre, pas de crash

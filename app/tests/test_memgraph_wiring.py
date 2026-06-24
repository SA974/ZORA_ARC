"""Tests du câblage extraction MemGraphRAG dans l'ingestion PDF (sans LLM ni DB réels)."""
from __future__ import annotations

from types import SimpleNamespace

import app.services.ingestion_pipeline as ip_mod
from app.services.document_ingestion import _extract_chunks_to_memgraph


def _chunk(text):
    return SimpleNamespace(content=text)


class _FakePipeline:
    def __init__(self, *, configured=True, fail_on=None):
        self._configured = configured
        self._fail_on = fail_on

    def configured(self):
        return self._configured

    def extract_and_store(self, content, *, source_document_id=None, source_chunk_id=None, detect_conflicts=False):
        if self._fail_on and source_chunk_id == self._fail_on:
            raise RuntimeError("LLM timeout simulé")
        return {"entities": 2, "facts": 3, "conflicts": [{"x": 1}]}


def test_wiring_aggregates(monkeypatch):
    monkeypatch.setattr(ip_mod, "IngestionPipeline", lambda: _FakePipeline())
    pairs = [(_chunk("a"), "c1"), (_chunk("b"), "c2")]
    r = _extract_chunks_to_memgraph(pairs, "doc1")
    assert r["status"] == "done"
    assert r["entities"] == 4 and r["facts"] == 6 and r["conflicts"] == 2 and r["errors"] == 0


def test_wiring_isolates_errors(monkeypatch):
    monkeypatch.setattr(ip_mod, "IngestionPipeline", lambda: _FakePipeline(fail_on="c2"))
    pairs = [(_chunk("a"), "c1"), (_chunk("b"), "c2"), (_chunk("c"), "c3")]
    r = _extract_chunks_to_memgraph(pairs, "doc1")
    # c2 échoue mais c1 et c3 réussissent -> 4 entités, 6 faits, 1 erreur isolée
    assert r["entities"] == 4 and r["facts"] == 6 and r["errors"] == 1


def test_wiring_skipped_when_llm_unconfigured(monkeypatch):
    monkeypatch.setattr(ip_mod, "IngestionPipeline", lambda: _FakePipeline(configured=False))
    r = _extract_chunks_to_memgraph([(_chunk("a"), "c1")], "doc1")
    assert r["status"] == "skipped_llm_not_configured" and r["entities"] == 0

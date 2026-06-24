"""Tests des fonctions pures du PPR conforme MemGraphRAG (sans DB ni Ollama)."""
from __future__ import annotations

from app.services.memgraph_ppr import _normalize, entity_init


def test_entity_init_zero_without_facts():
    assert entity_init([], 0) == 0.0


def test_entity_init_hub_suppression_monotonic():
    """À similarité égale, une entité plus connectée (hub) est davantage atténuée."""
    low_degree = entity_init([0.8, 0.8], degree=2)
    high_degree = entity_init([0.8, 0.8], degree=50)
    assert high_degree < low_degree


def test_entity_init_increases_with_similarity():
    assert entity_init([0.9], 3) > entity_init([0.2], 3)


def test_normalize_sums_to_one():
    out = _normalize({"a": 1.0, "b": 3.0})
    assert abs(sum(out.values()) - 1.0) < 1e-9
    assert out["b"] > out["a"]


def test_normalize_drops_nonpositive_and_handles_empty():
    assert _normalize({"a": 0.0, "b": -1.0}) == {}
    out = _normalize({"a": 2.0, "b": 0.0})
    assert out == {"a": 1.0}

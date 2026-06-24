"""Tests de la fonction de score H-MEM (pure, sans DB)."""
from __future__ import annotations

from app.services.hmem_retrieval import score_candidate


def test_score_bounds():
    assert abs(score_candidate(1.0, 1.0, 1.0) - 1.0) < 1e-9   # 0.6+0.3+0.1 (float)
    assert score_candidate(0.0, 0.0, 0.0) == 0.0


def test_score_monotonic_in_similarity():
    low = score_candidate(0.2, 0.5)
    high = score_candidate(0.9, 0.5)
    assert high > low


def test_salience_decay_lowers_score():
    fresh = score_candidate(0.8, 1.0)
    decayed = score_candidate(0.8, 0.2)
    assert fresh > decayed


def test_weights_default_convention():
    # alpha+beta+gamma = 1 -> entrées maximales donnent ~1.0
    assert abs(score_candidate(1.0, 1.0, 1.0) - 1.0) < 1e-9
    # la similarité (alpha=0.6) pèse plus que la salience (beta=0.3)
    assert score_candidate(1.0, 0.0, 0.0) > score_candidate(0.0, 1.0, 0.0)


def test_clamped_above_one():
    # même avec des entrées > 1 (théoriques), le score reste borné
    assert score_candidate(2.0, 2.0, 2.0) == 1.0

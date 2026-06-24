"""Tests des fonctions pures de détection de conflits."""
from __future__ import annotations

from app.services.conflict_service import _has_negation, _is_contradict_object


def test_has_negation():
    assert _has_negation("not alive")
    assert _has_negation("is alive, no")
    assert _has_negation("n'a pas") or _has_negation("ne sait pas")
    assert not _has_negation("knowledge")


def test_is_contradict_object_negation():
    """Objets contradictoires par négation : "is Y" vs "is NOT Y"."""
    assert _is_contradict_object("is alive", "is not alive")
    assert _is_contradict_object("yes", "not yes")
    assert not _is_contradict_object("is alive", "is happy")


def test_is_contradict_object_symmetric():
    assert _is_contradict_object("not alive", "is alive") == _is_contradict_object("is alive", "not alive")


def test_conflict_service_threshold():
    """Le seuil CONFLICT_SIM_THRESHOLD doit être importable."""
    from app.services.conflict_service import CONFLICT_SIM_THRESHOLD
    assert 0.5 < CONFLICT_SIM_THRESHOLD <= 1.0


def test_schema_gating_threshold():
    """Le seuil FREQUENCY_THRESHOLD doit être importable et > 0."""
    from app.services.schema_gating import FREQUENCY_THRESHOLD
    assert FREQUENCY_THRESHOLD > 0

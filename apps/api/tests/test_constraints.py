"""Tests for ConstraintManager."""

from __future__ import annotations

from app.schemas.constraints import (
    Constraints,
    HardConstraints,
    PreferencePatch,
    SoftPreferences,
)
from app.services.constraints import ConstraintManager


def test_merge_keeps_unrelated_fields_when_budget_changes():
    manager = ConstraintManager(
        Constraints(
            hard=HardConstraints(
                bedrooms=2,
                locality="Koramangala",
                max_rent=35000,
                must_have_amenities=["parking"],
            )
        )
    )
    updated = manager.merge(
        PreferencePatch(hard=HardConstraints(max_rent=40000))
    )
    assert updated.hard.max_rent == 40000
    assert updated.hard.bedrooms == 2
    assert updated.hard.locality == "Koramangala"
    assert updated.hard.must_have_amenities == ["parking"]


def test_clarification_counter_caps_at_five():
    manager = ConstraintManager(max_clarifications=5)
    for _ in range(5):
        assert manager.can_ask_clarification() is True
        manager.record_clarification()
    assert manager.clarification_count == 5
    assert manager.can_ask_clarification() is False
    manager.record_clarification()  # no-op beyond cap
    assert manager.clarification_count == 5


def test_is_search_ready_requires_critical_fields():
    manager = ConstraintManager()
    assert manager.is_search_ready() is False
    assert set(manager.missing_critical()) == {"bedrooms", "locality", "max_rent"}

    manager.merge(
        PreferencePatch(
            hard=HardConstraints(bedrooms=2, locality="Koramangala", max_rent=35000)
        )
    )
    assert manager.missing_critical() == []
    assert manager.is_search_ready() is True


def test_merge_soft_prefs_and_amenities_union():
    manager = ConstraintManager(
        Constraints(hard=HardConstraints(must_have_amenities=["parking"]))
    )
    manager.merge(
        PreferencePatch(
            hard=HardConstraints(must_have_amenities=["balcony"]),
            soft=SoftPreferences(pet_friendly=True),
        )
    )
    assert manager.constraints.hard.must_have_amenities == ["parking", "balcony"]
    assert manager.constraints.soft.pet_friendly is True

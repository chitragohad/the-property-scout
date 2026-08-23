"""Intent + preference extraction tests (offline heuristics)."""

from __future__ import annotations

from app.services.extract import extract_preferences_heuristic
from app.services.intent import classify_intent_heuristic


def test_extract_canonical_spoken_line():
    text = (
        "I'm looking for a 2BHK in Koramangala under 35,000. "
        "I need parking and I want it close to a metro station."
    )
    patch = extract_preferences_heuristic(text)
    assert patch.hard is not None
    assert patch.hard.bedrooms == 2
    assert patch.hard.locality == "Koramangala"
    assert patch.hard.max_rent == 35000
    assert "parking" in [a.lower() for a in patch.hard.must_have_amenities]
    assert patch.soft is not None
    assert patch.soft.near_metro is True


def test_intent_confirm_and_why_and_refine():
    assert classify_intent_heuristic("yes, confirm that") == "confirm_search"
    assert classify_intent_heuristic("why the first one?") == "ask_why"
    assert (
        classify_intent_heuristic(
            "actually make the budget under 30000",
            phase="shortlist",
        )
        == "refine_constraints"
    )
    assert (
        classify_intent_heuristic(
            "under 25000",
            phase="shortlist",
        )
        == "refine_constraints"
    )
    assert (
        classify_intent_heuristic(
            "remove the first one",
            phase="shortlist",
        )
        == "remove_listing"
    )
    assert classify_intent_heuristic("what's the neighborhood like?") == "ask_neighborhood"
    assert classify_intent_heuristic("book a visit Saturday") == "book_visit"


def test_clarify_phase_maps_to_clarify_answer():
    assert (
        classify_intent_heuristic(
            "Koramangala",
            phase="clarifying",
            missing_critical=["locality"],
        )
        == "clarify_answer"
    )

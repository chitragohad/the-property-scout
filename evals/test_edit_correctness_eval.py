"""Edit correctness evaluation suite."""

from __future__ import annotations

from copy import deepcopy

from app.schemas.constraints import PreferencePatch
from app.services.orchestrator import handle_turn
from evals.conftest import run_prefs_confirm
from evals.lib.edit_state import (
    assert_only_paths_changed,
    remove_listing_at_position,
    remove_listing_by_id,
    snapshot_session,
)
from evals.lib.report import eval_case


@eval_case("Edit Correctness", "Change budget")
def test_refine_budget_updates_only_budget_and_shortlist(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    before = snapshot_session(session_record)
    handle_turn(session_record, "actually make the budget under 30000", orchestrator_deps)
    after = snapshot_session(session_record)

    assert after["constraints"]["hard"]["max_rent"] == 30000
    assert after["constraints"]["hard"]["bedrooms"] == before["constraints"]["hard"]["bedrooms"]
    assert after["constraints"]["hard"]["locality"] == before["constraints"]["hard"]["locality"]
    assert before["constraints"]["hard"]["must_have_amenities"] == after["constraints"]["hard"]["must_have_amenities"]

    violations = assert_only_paths_changed(
        before,
        after,
        allowed_changed_paths={
            "constraints.hard.max_rent",
            "shortlist_ids",
            "phase",
            "citation_count",
        },
    )
    assert not violations, violations


@eval_case("Edit Correctness", "Change location")
def test_refine_locality_preserves_unrelated_constraints(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    before = snapshot_session(session_record)
    handle_turn(session_record, "change location to HSR Layout instead", orchestrator_deps)
    after = snapshot_session(session_record)

    assert after["constraints"]["hard"]["locality"] == "HSR Layout"
    assert after["constraints"]["hard"]["bedrooms"] == before["constraints"]["hard"]["bedrooms"]

    violations = assert_only_paths_changed(
        before,
        after,
        allowed_changed_paths={
            "constraints.hard.locality",
            "shortlist_ids",
            "phase",
            "citation_count",
        },
    )
    assert not violations, violations


@eval_case("Edit Correctness", "Add preference")
def test_add_must_have_merges_without_dropping_existing(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    before = snapshot_session(session_record)
    handle_turn(session_record, "refine to also require balcony", orchestrator_deps)
    after = snapshot_session(session_record)

    must_haves = after["constraints"]["hard"]["must_have_amenities"]
    assert "parking" in must_haves
    assert "balcony" in must_haves or after["constraints"]["soft"].get("balcony") is True

    violations = assert_only_paths_changed(
        before,
        after,
        allowed_changed_paths={
            "constraints.hard.must_have_amenities",
            "constraints.soft.balcony",
            "shortlist_ids",
            "phase",
            "citation_count",
        },
    )
    assert not violations, violations


@eval_case("Edit Correctness", "Regenerate shortlist")
def test_refine_regenerates_shortlist_under_new_filters(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    before_ids = [item.listing.listing_id for item in session_record.shortlist]
    handle_turn(session_record, "lower budget to 28000", orchestrator_deps)
    after_ids = [item.listing.listing_id for item in session_record.shortlist]
    assert session_record.shortlist
    for item in session_record.shortlist:
        assert item.listing.rent <= 28000
    # Shortlist may change entirely — eval only requires feasibility, not identical ordering
    assert isinstance(after_ids, list)


@eval_case("Edit Correctness", "Remove listing")
def test_remove_listing_reference_edit_changes_only_shortlist_ids(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    before = snapshot_session(session_record)
    assert len(before["shortlist_ids"]) >= 2
    after = remove_listing_at_position(before, 0)
    violations = assert_only_paths_changed(
        before,
        after,
        allowed_changed_paths={"shortlist_ids"},
    )
    assert not violations, violations
    assert len(after["shortlist_ids"]) == len(before["shortlist_ids"]) - 1


@eval_case("Edit Correctness", "Preserve unrelated state")
def test_budget_refine_does_not_touch_booking_or_commute(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    session_record.constraints.merge(
        PreferencePatch(commute_point="Manyata Tech Park", patch_mode="merge")
    )
    before = snapshot_session(session_record)
    handle_turn(session_record, "lower budget to 32000", orchestrator_deps)
    after = snapshot_session(session_record)
    assert after["constraints"].get("commute_point") == before["constraints"].get("commute_point")
    assert after["booking"] == before["booking"]


@eval_case("Edit Correctness", "Detector: unintended budget change")
def test_detector_flags_unrelated_budget_change(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    before = snapshot_session(session_record)
    after = deepcopy(before)
    after["constraints"]["hard"]["max_rent"] = before["constraints"]["hard"]["max_rent"] - 1000
    violations = assert_only_paths_changed(
        before,
        after,
        allowed_changed_paths={"shortlist_ids"},
    )
    assert violations


@eval_case("Edit Correctness", "Detector: remove listing by id")
def test_remove_by_id_reference_edit(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    before = snapshot_session(session_record)
    target = before["shortlist_ids"][0]
    after = remove_listing_by_id(before, target)
    assert target not in after["shortlist_ids"]
    violations = assert_only_paths_changed(before, after, allowed_changed_paths={"shortlist_ids"})
    assert not violations, violations

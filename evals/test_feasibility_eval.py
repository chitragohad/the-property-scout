"""Feasibility evaluation suite."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.schemas.session import ShortlistItem
from app.services.orchestrator import handle_turn
from evals.conftest import run_prefs_confirm
from evals.lib.feasibility import (
    METRO_POI_NEAR_METRO_TOLERANCE_M,
    check_budget_compliance,
    check_commute_consistency,
    check_must_have_compliance,
    run_feasibility_checks,
)
from evals.lib.report import eval_case


@eval_case("Feasibility", "Budget compliance")
def test_shortlist_respects_max_budget(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    assert session_record.shortlist
    violations = check_budget_compliance(
        session_record.shortlist,
        session_record.constraints.constraints.hard.max_rent,
    )
    assert not violations, violations


@eval_case("Feasibility", "Must-have compliance")
def test_shortlist_satisfies_must_haves(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    violations = check_must_have_compliance(
        session_record.shortlist,
        session_record.constraints.constraints,
    )
    assert not violations, violations


@eval_case("Feasibility", "Commute consistency")
def test_transit_claims_match_osm_dataset(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    violations = check_commute_consistency(
        session_record.shortlist,
        session_record.constraints.constraints,
    )
    assert not violations, violations


@eval_case("Feasibility", "Detector: budget violation")
def test_detector_flags_over_budget_listing(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    assert session_record.shortlist
    bad = deepcopy(session_record.shortlist[0])
    bad.listing.rent = session_record.constraints.constraints.hard.max_rent + 5000
    violations = check_budget_compliance(
        [bad],
        session_record.constraints.constraints.hard.max_rent,
    )
    assert violations
    assert violations[0].code == "budget_exceeded"


@eval_case("Feasibility", "Detector: must-have violation")
def test_detector_flags_missing_must_have(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    bad = deepcopy(session_record.shortlist[0])
    bad.listing.amenities = [a for a in bad.listing.amenities if a != "parking"]
    violations = check_must_have_compliance(
        [bad],
        session_record.constraints.constraints,
    )
    assert any(v.code == "must_have_missing" for v in violations)


@eval_case("Feasibility", "Detector: unsupported commute minutes")
def test_detector_flags_unsupported_minute_claim(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    bad = deepcopy(session_record.shortlist[0])
    bad.osm = None
    bad.rank.reason = "Only 12 minutes to Manyata Tech Park by car."
    violations = check_commute_consistency([bad], session_record.constraints.constraints)
    assert any(v.code == "unsupported_commute_minutes" for v in violations)


def test_metro_tolerance_constant_documented():
    assert METRO_POI_NEAR_METRO_TOLERANCE_M == 800


def test_end_to_end_feasibility_after_refine(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    handle_turn(session_record, "actually make the budget under 30000", orchestrator_deps)
    violations = run_feasibility_checks(
        session_record.shortlist,
        session_record.constraints.constraints,
    )
    assert not violations, violations

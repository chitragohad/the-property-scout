"""Grounding & hallucination evaluation suite."""

from __future__ import annotations

from copy import deepcopy

from app.schemas.listing import Listing, NeighborhoodGuidance, NeighborhoodSource
from app.schemas.osm import NeighborhoodNote
from app.schemas.ranking import RankResult
from app.schemas.session import ShortlistItem
from app.services.rag import UNVERIFIABLE
from evals.conftest import run_prefs_confirm
from evals.lib.dataset import authoritative_listing_ids
from evals.lib.grounding import (
    check_availability_grounded,
    check_listing_ids_grounded,
    check_missing_neighborhood_uncertainty,
    check_neighborhood_citations,
    run_grounding_checks,
)
from evals.lib.report import eval_case


@eval_case("Grounding & Hallucination", "Listing IDs grounded")
def test_shortlist_ids_exist_in_authoritative_dataset(session_record, orchestrator_deps, db_session):
    run_prefs_confirm(session_record, orchestrator_deps)
    violations = check_listing_ids_grounded(session_record.shortlist, db=db_session)
    assert not violations, violations


@eval_case("Grounding & Hallucination", "Availability grounded")
def test_shortlist_only_contains_available_listings(session_record, orchestrator_deps, db_session):
    run_prefs_confirm(session_record, orchestrator_deps)
    violations = check_availability_grounded(session_record.shortlist, db=db_session)
    assert not violations, violations


@eval_case("Grounding & Hallucination", "Neighborhood citations")
def test_neighborhood_notes_have_valid_sources(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    violations = check_neighborhood_citations(session_record.shortlist)
    assert not violations, violations


@eval_case("Grounding & Hallucination", "Missing neighborhood uncertainty")
def test_unverified_localities_surface_uncertainty(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    # Force an unverified locality note onto first card to validate policy
    item = session_record.shortlist[0]
    item.neighborhood_notes = [
        NeighborhoodNote(
            topic="safety",
            text=UNVERIFIABLE,
            citation_id="unverified",
        )
    ]
    violations = check_missing_neighborhood_uncertainty(
        [item],
        unverified_localities=[item.listing.locality],
    )
    assert not violations, violations


@eval_case("Grounding & Hallucination", "Detector: fake listing ID")
def test_detector_flags_unknown_listing_id(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    fake = deepcopy(session_record.shortlist[0])
    fake.listing.listing_id = "fake-listing-999"
    violations = check_listing_ids_grounded([fake])
    assert violations
    assert violations[0].code == "unknown_listing_id"


@eval_case("Grounding & Hallucination", "Detector: unavailable listing claim")
def test_detector_flags_unavailable_listing(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    bad = deepcopy(session_record.shortlist[0])
    bad.listing.availability_status = "leased"
    violations = check_availability_grounded([bad])
    assert any(v.code == "claimed_available_when_not" for v in violations)


@eval_case("Grounding & Hallucination", "Detector: unsupported neighborhood citation")
def test_detector_flags_invalid_citation_id(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    bad = deepcopy(session_record.shortlist[0])
    bad.neighborhood_notes = [
        NeighborhoodNote(
            topic="safety",
            text="This area is extremely safe at all hours.",
            citation_id="made-up-source",
        )
    ]
    violations = check_neighborhood_citations([bad])
    assert violations


@eval_case("Grounding & Hallucination", "Detector: missing uncertainty language")
def test_detector_flags_hallucinated_neighborhood_without_rag(session_record, orchestrator_deps):
    run_prefs_confirm(session_record, orchestrator_deps)
    bad = deepcopy(session_record.shortlist[0])
    bad.neighborhood_notes = [
        NeighborhoodNote(
            topic="safety",
            text="Definitely the safest block in Bengaluru.",
            citation_id="unverified",
        )
    ]
    violations = check_missing_neighborhood_uncertainty(
        [bad],
        unverified_localities=[bad.listing.locality],
    )
    assert violations


def test_end_to_end_grounding_after_search(session_record, orchestrator_deps, db_session):
    run_prefs_confirm(session_record, orchestrator_deps)
    violations = run_grounding_checks(session_record.shortlist, db=db_session)
    assert not violations, violations


def _synthetic_ungrounded_item() -> ShortlistItem:
    listing = Listing(
        listing_id="synthetic-not-in-db",
        source_url="https://example.invalid/listing",
        location="Bengaluru",
        locality="Nowhere",
        rent=25000,
        bedrooms=2,
        furnishing="unfurnished",
        amenities=["parking"],
        society_name="Ghost Towers",
        square_footage=900,
        available_from="2026-08-22",
        deposit_amount=50000,
        listing_type="whole flat",
        food_preference="any",
        smoking_preference="any",
        neighborhood_guidance=NeighborhoodGuidance(
            locality="Nowhere",
            safety="unknown",
            amenities="unknown",
            transit_character="unknown",
            sources=[
                NeighborhoodSource(
                    title="Fake source",
                    url="https://example.invalid/source",
                    snippet="not in RAG",
                )
            ],
        ),
        availability_status="available",
        latitude=12.9,
        longitude=77.6,
    )
    rank = RankResult(
        listing_id=listing.listing_id,
        score=90,
        matched=["within budget"],
        missing=[],
        excluded=False,
        exclusion_reasons=[],
        reason="Synthetic test listing.",
    )
    return ShortlistItem(listing=listing, rank=rank, citations=[])


def test_synthetic_item_fails_multiple_grounding_checks(db_session):
    item = _synthetic_ungrounded_item()
    assert item.listing.listing_id not in authoritative_listing_ids(db_session)
    violations = run_grounding_checks([item], unverified_localities=["Nowhere"], db=db_session)
    assert len(violations) >= 2

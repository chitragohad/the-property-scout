"""Tests for per-listing contextual copy."""

from __future__ import annotations

from app.schemas.listing import Listing, NeighborhoodGuidance
from app.schemas.osm import OsmContext, OsmPoi
from app.schemas.ranking import RankResult
from app.services.listing_context import (
    build_listing_neighborhood_notes,
    build_listing_reason,
    build_poi_summary,
)
from app.services.ranking import Enrichment


def _listing(listing_id: str, society: str, amenities: list[str]) -> Listing:
    return Listing(
        listing_id=listing_id,
        source_url=f"https://bengaluru.rent/#listing-{listing_id}",
        location="Bengaluru",
        locality="Koramangala",
        rent=28000,
        bedrooms=2,
        furnishing="furnished",
        amenities=amenities,
        society_name=society,
        square_footage=980,
        available_from="2026-09-01",
        deposit_amount=84000,
        listing_type="whole flat",
        food_preference="any",
        smoking_preference="any",
        neighborhood_guidance=NeighborhoodGuidance(
            locality="Koramangala",
            safety="Busy mixed area.",
            amenities="Retail nearby.",
            transit_character="Bus and metro catchments.",
            sources=[],
        ),
        availability_status="available",
        latitude=12.9352,
        longitude=77.6245,
    )


def test_build_listing_reason_mentions_society_and_amenities():
    listing = _listing("blr-km-202", "5th Block Nest", ["parking", "power-backup"])
    rank = RankResult(
        listing_id=listing.listing_id,
        score=73,
        matched=["within budget", "2BHK"],
        missing=[],
        excluded=False,
        exclusion_reasons=[],
        reason="placeholder",
    )
    enrich = Enrichment(
        listing_id=listing.listing_id,
        near_metro=True,
        transit_poi_count=1,
        notes=["Nearest metro: Demo Metro (~250m)"],
    )
    reason = build_listing_reason(listing, rank, enrich)
    assert "5th Block Nest" in reason
    assert "parking" in reason
    assert "Demo Metro" in reason


def test_neighborhood_notes_differ_by_listing_and_osm():
    osm_a = OsmContext(
        listing_id="a",
        pois=[
            OsmPoi(name="Metro A", category="metro", lat=1, lon=1, distance_m=200),
            OsmPoi(name="Store A", category="grocery", lat=1, lon=1, distance_m=150),
        ],
        raw_call_id="mock-a",
    )
    osm_b = OsmContext(
        listing_id="b",
        pois=[
            OsmPoi(name="Metro B", category="metro", lat=1, lon=1, distance_m=400),
            OsmPoi(name="Store B", category="grocery", lat=1, lon=1, distance_m=320),
        ],
        raw_call_id="mock-b",
    )
    listing_a = _listing("a", "5th Block Nest", ["parking", "power-backup"])
    listing_b = _listing("b", "Koramangala Clubside", ["parking", "security"])

    notes_a = build_listing_neighborhood_notes(listing_a, osm_a, [], None)
    notes_b = build_listing_neighborhood_notes(listing_b, osm_b, [], None)

    transit_a = next(n for n in notes_a if n.topic == "transit")
    transit_b = next(n for n in notes_b if n.topic == "transit")
    assert "Metro A" in transit_a.text
    assert "Metro B" in transit_b.text
    assert transit_a.text != transit_b.text

    amen_a = next(n for n in notes_a if n.topic == "amenities")
    amen_b = next(n for n in notes_b if n.topic == "amenities")
    assert "power-backup" in amen_a.text
    assert "security" in amen_b.text


def test_build_poi_summary():
    osm = OsmContext(
        listing_id="x",
        pois=[
            OsmPoi(name="Kormangala", category="metro", lat=1, lon=1, distance_m=250),
            OsmPoi(name="Fresh Mart", category="grocery", lat=1, lon=1, distance_m=180),
        ],
        raw_call_id="mock",
    )
    summary = build_poi_summary(osm)
    assert summary is not None
    assert "250m" in summary
    assert "180m" in summary

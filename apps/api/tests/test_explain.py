"""Grounded explanation tests."""

from __future__ import annotations

from app.schemas.listing import Listing, NeighborhoodGuidance
from app.schemas.osm import NeighborhoodNote, OsmContext, OsmPoi
from app.schemas.ranking import Citation, RankResult
from app.schemas.session import ShortlistItem
from app.services.explain import build_evidence, explain_from_evidence
from app.services.rag import UNVERIFIABLE


def _item(*, with_rag: bool = True) -> ShortlistItem:
    listing = Listing(
        listing_id="blr-km-201",
        source_url="https://bengaluru.rent/#x",
        location="Bengaluru",
        locality="Koramangala",
        rent=32000,
        bedrooms=2,
        furnishing="semi-furnished",
        amenities=["parking"],
        society_name="Sony Signal Residency",
        square_footage=1050,
        available_from="2026-08-21",
        deposit_amount=64000,
        listing_type="whole flat",
        food_preference="any",
        smoking_preference="any",
        neighborhood_guidance=NeighborhoodGuidance(
            locality="Koramangala",
            safety="s",
            amenities="a",
            transit_character="t",
            sources=[],
        ),
        availability_status="available",
        latitude=12.93,
        longitude=77.62,
    )
    rank = RankResult(
        listing_id="blr-km-201",
        score=88.0,
        matched=["2BHK", "within budget", "parking"],
        missing=[],
        excluded=False,
        exclusion_reasons=[],
        reason="Strong match for all mandatory requirements.",
    )
    citations = []
    notes = []
    if with_rag:
        citations = [
            Citation(
                id="km-safety",
                title="Koramangala — Wikipedia",
                url="https://en.wikipedia.org/wiki/Koramangala",
                snippet="busy area",
                locality="Koramangala",
                topic="safety",
            )
        ]
        notes = [
            NeighborhoodNote(
                topic="safety",
                text="Koramangala is a busy well-lit mixed area.",
                citation_id="km-safety",
            )
        ]
    else:
        notes = [
            NeighborhoodNote(
                topic="character",
                text=UNVERIFIABLE,
                citation_id="unverified",
            )
        ]
    return ShortlistItem(
        listing=listing,
        rank=rank,
        citations=citations,
        osm=OsmContext(
            listing_id="blr-km-201",
            pois=[
                OsmPoi(
                    name="Demo Metro",
                    category="metro",
                    lat=12.93,
                    lon=77.62,
                    distance_m=200,
                )
            ],
            raw_call_id="test-1",
        ),
        neighborhood_notes=notes,
    )


def test_why_first_references_matched_reasons():
    text = explain_from_evidence(build_evidence(_item()), question="why the first one")
    assert "Sony Signal Residency" in text
    assert "88" in text or "Strong match" in text
    assert "parking" in text.lower() or "2BHK" in text


def test_missing_rag_neighborhood_fallback():
    text = explain_from_evidence(
        build_evidence(_item(with_rag=False)),
        question="what's the neighborhood like",
    )
    assert text == UNVERIFIABLE

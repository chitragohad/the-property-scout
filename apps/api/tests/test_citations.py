"""Citation helpers for Sources panel display."""

from __future__ import annotations

from app.schemas.listing import Listing, NeighborhoodGuidance
from app.schemas.osm import OsmContext, OsmPoi
from app.schemas.ranking import Citation
from app.services.citations import (
    build_listing_source_citation,
    build_osm_citation,
    display_citations_for_listing,
    is_wikipedia_url,
)


def _listing() -> Listing:
    return Listing(
        listing_id="blr-test-1",
        source_url="https://bengaluru.rent/#listing-blr-test-1",
        location="Bengaluru",
        locality="Koramangala",
        rent=30000,
        bedrooms=2,
        furnishing="furnished",
        amenities=["parking"],
        society_name="Soc",
        square_footage=1000,
        available_from="2026-08-21",
        deposit_amount=60000,
        listing_type="whole flat",
        food_preference="any",
        smoking_preference="any",
        neighborhood_guidance=NeighborhoodGuidance(
            locality="Koramangala",
            safety="safe",
            amenities="shops",
            transit_character="metro",
            sources=[],
        ),
        availability_status="available",
        latitude=12.9352,
        longitude=77.6245,
    )


def test_build_listing_source_citation_links_to_bengaluru_rent():
    listing = _listing()
    cite = build_listing_source_citation(listing)
    assert cite is not None
    assert cite.title == "bengaluru.rent — listing"
    assert cite.url == listing.source_url
    assert "bengaluru.rent" in cite.url
    assert cite.topic == "listing"


def test_build_osm_citation_links_to_map():
    listing = _listing()
    ctx = OsmContext(
        listing_id=listing.listing_id,
        pois=[
            OsmPoi(name="Demo Metro", category="metro", lat=12.93, lon=77.62, distance_m=200),
        ],
        raw_call_id="mock-1",
    )
    cite = build_osm_citation(listing, ctx)
    assert cite is not None
    assert cite.title == "OpenStreetMap — nearby POIs"
    assert "openstreetmap.org" in cite.url
    assert "12.9352" in cite.url
    assert cite.topic == "osm"


def test_display_citations_prefers_osm_over_wikipedia():
    listing = _listing()
    ctx = OsmContext(listing_id=listing.listing_id, pois=[], raw_call_id="mock-2")
    rag = [
        Citation(
            id="wiki-km",
            title="Koramangala — Wikipedia",
            url="https://en.wikipedia.org/wiki/Koramangala",
            snippet="Neighbourhood overview.",
            locality="Koramangala",
            topic="safety",
        )
    ]
    cites = display_citations_for_listing(rag, listing, ctx)
    assert len(cites) == 2
    assert any("bengaluru.rent" in c.url for c in cites)
    assert any("openstreetmap.org" in c.url for c in cites)
    assert not any(is_wikipedia_url(c.url) for c in cites)

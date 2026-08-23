"""Unit tests for OSM service + Overpass client framing."""

from __future__ import annotations

import pytest

from app.schemas.listing import Listing, NeighborhoodGuidance
from app.schemas.osm import OsmContext, OsmPoi
from app.services.osm import OsmService


def _listing() -> Listing:
    return Listing(
        listing_id="blr-km-201",
        source_url="https://bengaluru.rent/#listing-km-201",
        location="Bengaluru",
        locality="Koramangala",
        rent=32000,
        bedrooms=2,
        furnishing="semi-furnished",
        amenities=["parking"],
        society_name="Test",
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
        latitude=12.9352,
        longitude=77.6245,
    )


class _FakeClient:
    def __init__(self, ctx: OsmContext) -> None:
        self.ctx = ctx
        self.calls = 0

    def nearby(self, *, listing_id: str, lat: float, lon: float, radius_m: int = 800) -> OsmContext:
        self.calls += 1
        return self.ctx


def test_osm_cache_by_listing_and_radius():
    ctx = OsmContext(
        listing_id="blr-km-201",
        pois=[
            OsmPoi(
                name="Koramangala Metro",
                category="metro",
                lat=12.935,
                lon=77.625,
                distance_m=120,
            )
        ],
        raw_call_id="test-call-1",
    )
    client = _FakeClient(ctx)
    svc = OsmService(client=client)
    listing = _listing()
    a = svc.nearby_for_listing(listing, radius_m=800)
    b = svc.nearby_for_listing(listing, radius_m=800)
    assert a.raw_call_id == "test-call-1"
    assert client.calls == 1
    assert b.pois[0].category == "metro"
    svc.nearby_for_listing(listing, radius_m=1200)
    assert client.calls == 2


def test_empty_results_use_osm_framing():
    ctx = OsmContext(
        listing_id="blr-km-201",
        pois=[],
        raw_call_id="empty-1",
        empty_reason="Couldn't find nearby transit/POI in available OpenStreetMap data within 800m.",
    )
    svc = OsmService(client=_FakeClient(ctx))
    enrich = svc.enrichment_from_context(svc.nearby_for_listing(_listing()))
    assert enrich.near_metro is None
    assert enrich.transit_poi_count == 0
    assert "OpenStreetMap" in enrich.notes[0]


def test_enrichment_detects_metro():
    ctx = OsmContext(
        listing_id="blr-km-201",
        pois=[
            OsmPoi(name="Station", category="metro", lat=12.9, lon=77.6, distance_m=200),
            OsmPoi(name="Bus", category="transit", lat=12.9, lon=77.6, distance_m=80),
        ],
        raw_call_id="m1",
    )
    svc = OsmService(client=_FakeClient(ctx))
    enrich = svc.enrichment_from_context(ctx)
    assert enrich.near_metro is True
    assert enrich.transit_poi_count == 2


def test_live_overpass_koramangala_optional():
    """Optional live Overpass call — skipped unless RUN_OSM_LIVE=1."""
    import os
    import sys
    from pathlib import Path

    if os.getenv("RUN_OSM_LIVE") != "1":
        pytest.skip("Set RUN_OSM_LIVE=1 to hit Overpass")

    integ = Path(__file__).resolve().parents[3] / "integrations" / "osm-mcp"
    if str(integ) not in sys.path:
        sys.path.insert(0, str(integ))
    from client import OverpassOsmClient

    ctx = OverpassOsmClient().nearby(
        listing_id="blr-km-201",
        lat=12.9352,
        lon=77.6245,
        radius_m=800,
    )
    assert ctx.raw_call_id
    print(ctx.model_dump())

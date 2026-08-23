"""Enrichment pipeline: OSM + RAG → shortlist cards."""

from __future__ import annotations

from pathlib import Path

from app.schemas.constraints import Constraints, HardConstraints, SoftPreferences
from app.schemas.listing import Listing, NeighborhoodGuidance
from app.schemas.osm import OsmContext, OsmPoi
from app.services.enrichment import EnrichmentService
from app.services.osm import OsmService
from app.services.rag import RagService


def _listing(listing_id: str, locality: str, rent: int = 30000) -> Listing:
    return Listing(
        listing_id=listing_id,
        source_url=f"https://bengaluru.rent/#listing-{listing_id}",
        location="Bengaluru",
        locality=locality,
        rent=rent,
        bedrooms=2,
        furnishing="furnished",
        amenities=["parking", "balcony"],
        society_name="Soc",
        square_footage=1000,
        available_from="2026-08-21",
        deposit_amount=rent * 2,
        listing_type="whole flat",
        food_preference="any",
        smoking_preference="any",
        neighborhood_guidance=NeighborhoodGuidance(
            locality=locality,
            safety="safe area",
            amenities="shops nearby",
            transit_character="bus access",
            sources=[],
        ),
        availability_status="available",
        latitude=12.9352,
        longitude=77.6245,
    )


class _FakeOsm:
    def nearby(self, *, listing_id: str, lat: float, lon: float, radius_m: int = 800) -> OsmContext:
        return OsmContext(
            listing_id=listing_id,
            pois=[
                OsmPoi(
                    name="Demo Metro",
                    category="metro",
                    lat=lat,
                    lon=lon,
                    distance_m=250,
                )
            ],
            raw_call_id=f"mock-{listing_id}",
        )


def test_enrichment_fans_out_rag_per_locality(tmp_path: Path):
    # Build tiny index via worker helper
    import sys

    root = Path(__file__).resolve().parents[3]
    rag_worker = root / "workers" / "rag-index"
    if str(rag_worker) not in sys.path:
        sys.path.insert(0, str(rag_worker))
    from chunk_embed import build_index

    # Ensure normalized exists; build seed index into tmp
    index_path = build_index(include_seeds=True, raw_sources=[], out_path=tmp_path / "chunks.json")

    listings = [
        _listing("blr-km-201", "Koramangala", 32000),
        _listing("blr-km-202", "Koramangala", 28000),
        _listing("blr-hsr-301", "HSR Layout", 33000),
    ]
    constraints = Constraints(
        hard=HardConstraints(
            bedrooms=2,
            locality=None,
            max_rent=35000,
            must_have_amenities=["parking"],
        ),
        soft=SoftPreferences(near_metro=True),
    )
    svc = EnrichmentService(
        osm=OsmService(client=_FakeOsm()),
        rag=RagService(index_path=index_path),
    )
    result = svc.build_enriched_shortlist(listings, constraints, max_size=5)
    assert result.shortlist
    for item in result.shortlist:
        assert item.osm is not None
        assert item.osm.raw_call_id.startswith("mock-")
        assert item.osm.pois
        assert item.neighborhood_notes
        # Sources cite OpenStreetMap instead of Wikipedia RAG seeds
        if item.listing.locality.lower() in {"koramangala", "hsr layout"}:
            assert item.citations
            assert all(c.url for c in item.citations)
            assert any("openstreetmap.org" in c.url for c in item.citations)
            assert any("bengaluru.rent" in c.url for c in item.citations)
            assert not any("wikipedia.org" in c.url for c in item.citations)
    # Transit soft score should see near_metro from OSM
    assert any(e.near_metro is True for e in result.enrichment.values())

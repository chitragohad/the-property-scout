"""Tests for deterministic ranking."""

from __future__ import annotations

from app.schemas.constraints import Constraints, HardConstraints, SoftPreferences
from app.schemas.listing import Listing, NeighborhoodGuidance
from app.services.ranking import Enrichment, rank_listings


def _listing(
    listing_id: str,
    *,
    rent: int,
    bedrooms: int = 2,
    locality: str = "Koramangala",
    amenities: list[str] | None = None,
    availability: str = "available",
) -> Listing:
    return Listing(
        listing_id=listing_id,
        source_url=f"https://bengaluru.rent/#listing-{listing_id}",
        location="Bengaluru",
        locality=locality,
        rent=rent,
        bedrooms=bedrooms,
        furnishing="semi-furnished",
        amenities=amenities or ["parking"],
        society_name=f"Society {listing_id}",
        square_footage=1000,
        available_from="2026-09-01",
        deposit_amount=60000,
        listing_type="whole flat",
        food_preference="any",
        smoking_preference="no smoking",
        gender=None,
        neighborhood_guidance=NeighborhoodGuidance(
        locality="Koramangala",
        safety="Busy mixed residential-commercial area; verify building security.",
        amenities="Groceries, cafes, clinics nearby.",
        transit_character="Arterial road access with bus coverage; metro catchments nearby.",
        sources=[],
    ),
        availability_status=availability,
        latitude=12.93,
        longitude=77.62,
    )


def test_hard_failures_excluded_with_reasons():
    listings = [
        _listing("ok", rent=32000, amenities=["parking"]),
        _listing("over", rent=45000, amenities=["parking"]),
        _listing("no-park", rent=30000, amenities=["balcony"]),
        _listing("wrong-bhk", rent=30000, bedrooms=3, amenities=["parking"]),
        _listing("wrong-area", rent=30000, locality="HSR Layout", amenities=["parking"]),
    ]
    constraints = Constraints(
        hard=HardConstraints(
            bedrooms=2,
            locality="Koramangala",
            max_rent=35000,
            must_have_amenities=["parking"],
        )
    )
    ranked = rank_listings(listings, constraints)
    by_id = {r.listing_id: r for r in ranked}

    assert by_id["ok"].excluded is False
    assert by_id["over"].excluded is True
    assert "over budget" in by_id["over"].exclusion_reasons
    assert by_id["no-park"].excluded is True
    assert any("parking" in r for r in by_id["no-park"].exclusion_reasons)
    assert by_id["wrong-bhk"].excluded is True
    assert by_id["wrong-area"].excluded is True


def test_soft_prefs_change_order_without_excluding():
    listings = [
        _listing("with-balcony", rent=33000, amenities=["parking", "balcony"]),
        _listing("no-balcony", rent=30000, amenities=["parking"]),
    ]
    constraints = Constraints(
        hard=HardConstraints(
            bedrooms=2,
            locality="Koramangala",
            max_rent=35000,
            must_have_amenities=["parking"],
        ),
        soft=SoftPreferences(balcony=True),
    )
    ranked = [r for r in rank_listings(listings, constraints) if not r.excluded]
    assert [r.listing_id for r in ranked] == ["with-balcony", "no-balcony"]
    assert ranked[1].excluded is False
    assert "balcony" in ranked[1].missing


def test_each_result_has_matched_missing_reason():
    listings = [
        _listing("a", rent=32000, amenities=["parking"]),
        _listing("b", rent=40000, amenities=["parking"]),
    ]
    constraints = Constraints(
        hard=HardConstraints(
            bedrooms=2,
            locality="Koramangala",
            max_rent=35000,
            must_have_amenities=["parking"],
        ),
        soft=SoftPreferences(balcony=True),
    )
    ranked = rank_listings(listings, constraints)
    for result in ranked:
        assert isinstance(result.matched, list)
        assert isinstance(result.missing, list)
        assert isinstance(result.reason, str) and result.reason
        if result.excluded:
            assert result.exclusion_reasons


def test_transit_soft_uses_enrichment_without_inventing():
    listings = [_listing("metro", rent=32000), _listing("far", rent=31000)]
    constraints = Constraints(
        hard=HardConstraints(
            bedrooms=2,
            locality="Koramangala",
            max_rent=35000,
            must_have_amenities=["parking"],
        ),
        soft=SoftPreferences(near_metro=True),
    )
    enrichment = {
        "metro": Enrichment(listing_id="metro", near_metro=True, transit_poi_count=2),
        "far": Enrichment(listing_id="far", near_metro=False, transit_poi_count=0),
    }
    ranked = [r for r in rank_listings(listings, constraints, enrichment) if not r.excluded]
    assert ranked[0].listing_id == "metro"
    assert "near transit" in ranked[0].matched

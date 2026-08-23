"""Tests for shortlist builder and availability drops."""

from __future__ import annotations

from app.schemas.constraints import Constraints, HardConstraints, SoftPreferences
from app.schemas.listing import Listing, NeighborhoodGuidance
from app.services.shortlist import ShortlistService, build_shortlist


def _listing(
    listing_id: str,
    *,
    rent: int,
    amenities: list[str] | None = None,
    availability: str = "available",
    bedrooms: int = 2,
    locality: str = "Koramangala",
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


def test_build_shortlist_top_3_to_5_with_reasons():
    listings = [
        _listing("a", rent=28000, amenities=["parking", "balcony"]),
        _listing("b", rent=30000, amenities=["parking"]),
        _listing("c", rent=32000, amenities=["parking", "pet-friendly"]),
        _listing("d", rent=33000, amenities=["parking"]),
        _listing("e", rent=34000, amenities=["parking", "balcony"]),
        _listing("over", rent=45000, amenities=["parking"]),
        _listing("gone", rent=25000, amenities=["parking"], availability="not_for_rent"),
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
    state = build_shortlist(listings, constraints)
    assert 3 <= len(state.included) <= 5
    assert all(not item.rank.excluded for item in state.included)
    assert all(item.rank.reason for item in state.included)
    excluded_ids = {r.listing_id for r in state.excluded}
    assert "over" in excluded_ids
    assert "gone" in excluded_ids


def test_shortlist_service_persists_and_drops_unavailable():
    listings = [
        _listing("a", rent=28000),
        _listing("b", rent=30000),
        _listing("c", rent=32000),
    ]
    constraints = Constraints(
        hard=HardConstraints(
            bedrooms=2,
            locality="Koramangala",
            max_rent=35000,
            must_have_amenities=["parking"],
        )
    )
    service = ShortlistService()
    state = service.rebuild(listings, constraints)
    assert len(state.included) == 3

    updated = service.drop_unavailable({"a", "c"})
    assert updated is not None
    ids = {item.listing.listing_id for item in updated.included}
    assert ids == {"a", "c"}
    assert any(r.listing_id == "b" for r in updated.excluded)

"""Retrieval hard-constraint tests with seeded fixture DB."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

FIXTURES = [
    {
        "listing_id": "km-under-parking",
        "source_url": "https://bengaluru.rent/#listing-km-under-parking",
        "location": "Bengaluru",
        "locality": "Koramangala",
        "rent": 32000,
        "bedrooms": 2,
        "furnishing": "semi-furnished",
        "amenities": ["parking", "balcony"],
        "society_name": "A",
        "square_footage": 1000,
        "available_from": "2026-09-01",
        "deposit_amount": 60000,
        "listing_type": "whole flat",
        "food_preference": "any",
        "smoking_preference": "no smoking",
        "gender": None,
        "neighborhood_guidance": {
            "locality": "Koramangala",
            "safety": "Test safety note.",
            "amenities": "Test amenities note.",
            "transit_character": "Test transit note.",
            "sources": [],
        },
        "availability_status": "available",
        "latitude": 12.93,
        "longitude": 77.62,
    },
    {
        "listing_id": "km-over-budget",
        "source_url": "https://bengaluru.rent/#listing-km-over-budget",
        "location": "Bengaluru",
        "locality": "Koramangala",
        "rent": 45000,
        "bedrooms": 2,
        "furnishing": "furnished",
        "amenities": ["parking"],
        "society_name": "B",
        "square_footage": 1200,
        "available_from": "2026-09-01",
        "deposit_amount": 60000,
        "listing_type": "whole flat",
        "food_preference": "any",
        "smoking_preference": "no smoking",
        "gender": None,
        "neighborhood_guidance": {
            "locality": "Koramangala",
            "safety": "Test safety note.",
            "amenities": "Test amenities note.",
            "transit_character": "Test transit note.",
            "sources": [],
        },
        "availability_status": "available",
        "latitude": 12.94,
        "longitude": 77.62,
    },
    {
        "listing_id": "km-no-parking",
        "source_url": "https://bengaluru.rent/#listing-km-no-parking",
        "location": "Bengaluru",
        "locality": "Koramangala",
        "rent": 30000,
        "bedrooms": 2,
        "furnishing": "unfurnished",
        "amenities": ["balcony"],
        "society_name": "C",
        "square_footage": 900,
        "available_from": "2026-09-01",
        "deposit_amount": 60000,
        "listing_type": "whole flat",
        "food_preference": "any",
        "smoking_preference": "no smoking",
        "gender": None,
        "neighborhood_guidance": {
            "locality": "Koramangala",
            "safety": "Test safety note.",
            "amenities": "Test amenities note.",
            "transit_character": "Test transit note.",
            "sources": [],
        },
        "availability_status": "available",
        "latitude": 12.92,
        "longitude": 77.61,
    },
    {
        "listing_id": "hsr-2bhk",
        "source_url": "https://bengaluru.rent/#listing-hsr-2bhk",
        "location": "Bengaluru",
        "locality": "HSR Layout",
        "rent": 31000,
        "bedrooms": 2,
        "furnishing": "semi-furnished",
        "amenities": ["parking"],
        "society_name": "D",
        "square_footage": 1050,
        "available_from": "2026-09-01",
        "deposit_amount": 60000,
        "listing_type": "whole flat",
        "food_preference": "any",
        "smoking_preference": "no smoking",
        "gender": None,
        "neighborhood_guidance": {
            "locality": "Koramangala",
            "safety": "Test safety note.",
            "amenities": "Test amenities note.",
            "transit_character": "Test transit note.",
            "sources": [],
        },
        "availability_status": "available",
        "latitude": 12.91,
        "longitude": 77.64,
    },
    {
        "listing_id": "km-3bhk",
        "source_url": "https://bengaluru.rent/#listing-km-3bhk",
        "location": "Bengaluru",
        "locality": "Koramangala",
        "rent": 33000,
        "bedrooms": 3,
        "furnishing": "furnished",
        "amenities": ["parking"],
        "society_name": "E",
        "square_footage": 1400,
        "available_from": "2026-09-01",
        "deposit_amount": 60000,
        "listing_type": "whole flat",
        "food_preference": "any",
        "smoking_preference": "no smoking",
        "gender": None,
        "neighborhood_guidance": {
            "locality": "Koramangala",
            "safety": "Test safety note.",
            "amenities": "Test amenities note.",
            "transit_character": "Test transit note.",
            "sources": [],
        },
        "availability_status": "available",
        "latitude": 12.935,
        "longitude": 77.625,
    },
    {
        "listing_id": "km-unavailable",
        "source_url": "https://bengaluru.rent/#listing-km-unavailable",
        "location": "Bengaluru",
        "locality": "Koramangala",
        "rent": 25000,
        "bedrooms": 2,
        "furnishing": "furnished",
        "amenities": ["parking"],
        "society_name": "F",
        "square_footage": 1000,
        "available_from": "2026-09-01",
        "deposit_amount": 60000,
        "listing_type": "whole flat",
        "food_preference": "any",
        "smoking_preference": "no smoking",
        "gender": None,
        "neighborhood_guidance": {
            "locality": "Koramangala",
            "safety": "Test safety note.",
            "amenities": "Test amenities note.",
            "transit_character": "Test transit note.",
            "sources": [],
        },
        "availability_status": "not_for_rent",
        "latitude": 12.93,
        "longitude": 77.62,
    },
]


@pytest.fixture()
def db_session(tmp_path: Path) -> Session:
    db_file = tmp_path / "retrieval.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

    from app.config import get_settings
    from app.db.models import ListingRow
    from app.db.session import get_session_factory, init_db, reset_engine_cache

    get_settings.cache_clear()
    reset_engine_cache()
    init_db()

    factory = get_session_factory()
    with factory() as session:
        for item in FIXTURES:
            session.add(
                ListingRow(
                    listing_id=item["listing_id"],
                    source_url=item["source_url"],
                    location=item["location"],
                    locality=item["locality"],
                    rent=item["rent"],
                    bedrooms=item["bedrooms"],
                    furnishing=item["furnishing"],
                    amenities_json=json.dumps(item["amenities"]),
                    society_name=item["society_name"],
                    square_footage=item["square_footage"],
                    available_from=item["available_from"],
                    deposit_amount=item["deposit_amount"],
                    listing_type=item["listing_type"],
                    food_preference=item["food_preference"],
                    smoking_preference=item["smoking_preference"],
                    gender=item.get("gender"),
                    neighborhood_guidance_json=json.dumps(item["neighborhood_guidance"]),
                    availability_status=item["availability_status"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                )
            )
        session.commit()

        yield session

    get_settings.cache_clear()
    reset_engine_cache()
    os.environ.pop("DATABASE_URL", None)


def test_filters_budget_bedrooms_locality_parking(db_session: Session):
    from app.schemas.constraints import HardConstraints
    from app.services.retrieval import find_candidates

    constraints = HardConstraints(
        bedrooms=2,
        locality="Koramangala",
        max_rent=35000,
        must_have_amenities=["parking"],
    )
    results = find_candidates(db_session, constraints)
    ids = {item.listing_id for item in results}
    assert ids == {"km-under-parking"}
    assert "km-over-budget" not in ids
    assert "km-no-parking" not in ids
    assert "hsr-2bhk" not in ids
    assert "km-3bhk" not in ids
    assert "km-unavailable" not in ids


def test_hard_mismatch_never_appears(db_session: Session):
    from app.schemas.constraints import HardConstraints
    from app.services.retrieval import find_candidates

    constraints = HardConstraints(
        bedrooms=2,
        locality="Koramangala",
        max_rent=35000,
        must_have_amenities=["parking"],
    )
    results = find_candidates(db_session, constraints)
    for listing in results:
        assert listing.bedrooms == 2
        assert listing.rent <= 35000
        assert "koramangala" in listing.locality.lower()
        assert "parking" in [a.lower() for a in listing.amenities]
        assert listing.availability_status == "available"
        assert listing.source_url

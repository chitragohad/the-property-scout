"""Tests for amenity / availability normalization."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from normalize import (  # noqa: E402
    is_currently_available,
    normalize_amenities,
    normalize_listing,
)


def test_normalize_amenities_aliases():
    assert normalize_amenities(["Car Parking", "Pet Friendly", "Balconies"]) == [
        "parking",
        "pet-friendly",
        "balcony",
    ]


def test_excludes_not_for_rent():
    raw = {
        "id": "x1",
        "source_url": "https://bengaluru.rent/#listing-x1",
        "locality": "Koramangala",
        "rent": 30000,
        "bedrooms": 2,
        "availability_status": "Not for rent",
        "latitude": 12.9,
        "longitude": 77.6,
        "amenities": ["parking"],
        "society_name": "X",
        "furnishing": "furnished",
        "square_footage": 1000,
        "location": "Bengaluru",
        "available_from": "2026-09-01",
    }
    assert is_currently_available(raw) is False
    assert normalize_listing(raw) is None


def test_normalize_available_listing_scrubs_and_keeps_source_url():
    raw = {
        "id": "km-1",
        "source_url": "https://bengaluru.rent/#listing-km-1",
        "locality": "Koramangala",
        "rent": "₹35,000/month",
        "bedrooms": "2BHK",
        "availability_status": "available",
        "latitude": 12.9352,
        "longitude": 77.6245,
        "amenities": "Parking, Balcony",
        "society_name": "Test Society",
        "furnishing": "Semi-Furnished",
        "square_footage": 1100,
        "location": "Bengaluru",
        "available_from": "01/09/2026",
        "deposit_amount": "2 months",
        "listing_type": "room",
        "food_preference": "veg only",
        "smoking_preference": "no smoking",
        "gender": "female",
        "owner_name": "Leak",
        "phone": "9999999999",
    }
    result = normalize_listing(raw)
    assert result is not None
    assert result["rent"] == 35000
    assert result["bedrooms"] == 2
    assert result["amenities"] == ["parking", "balcony"]
    assert result["available_from"] == "2026-09-01"
    assert result["deposit_amount"] == 70000
    assert result["listing_type"] == "room in a flat"
    assert result["food_preference"] == "veg"
    assert result["smoking_preference"] == "no smoking"
    assert result["gender"] == "female"
    assert "neighborhood_guidance" in result
    assert result["neighborhood_guidance"]["locality"] == "Koramangala"
    assert result["neighborhood_guidance"]["safety"]
    assert result["neighborhood_guidance"]["amenities"]
    assert result["neighborhood_guidance"]["transit_character"]
    assert result["source_url"].startswith("https://bengaluru.rent/")
    assert "owner_name" not in result
    assert "phone" not in result

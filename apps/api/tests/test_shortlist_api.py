"""API acceptance: Koramangala 2BHK ≤35k + parking → 3–5 scored cards."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db, reset_engine_cache
from app.main import app

INGEST_ROOT = Path(__file__).resolve().parents[3] / "workers" / "ingest"


@pytest.fixture(scope="module", autouse=True)
def _seed_listings_db():
    if str(INGEST_ROOT) not in sys.path:
        sys.path.insert(0, str(INGEST_ROOT))
    reset_engine_cache()
    init_db()
    from upsert import run_ingest

    run_ingest(use_seed=True)
    yield
    reset_engine_cache()


client = TestClient(app)


def test_shortlist_search_koramangala_demo_constraints():
    payload = {
        "constraints": {
            "hard": {
                "bedrooms": 2,
                "locality": "Koramangala",
                "max_rent": 35000,
                "must_have_amenities": ["parking"],
            },
            "soft": {
                "near_metro": True,
                "balcony": None,
                "pet_friendly": None,
            },
            "commute_point": None,
        },
        "limit": 5,
        "enrich": False,
    }
    response = client.post("/shortlist/search", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert 3 <= body["count"] <= 5
    assert len(body["shortlist"]) == body["count"]
    for card in body["shortlist"]:
        listing = card["listing"]
        rank = card["rank"]
        assert listing["bedrooms"] == 2
        assert listing["rent"] <= 35000
        assert "koramangala" in listing["locality"].lower()
        assert "parking" in [a.lower() for a in listing["amenities"]]
        assert listing["available_from"]
        assert listing["deposit_amount"] >= 0
        assert listing["listing_type"] in {"whole flat", "room in a flat"}
        assert listing["food_preference"] in {"veg", "non-veg", "any"}
        assert listing["smoking_preference"] in {"no smoking", "smoking allowed", "any"}
        if listing["listing_type"] == "room in a flat":
            assert listing.get("gender") in {"male", "female", "any"}
        else:
            assert "gender" not in listing
        guidance = listing["neighborhood_guidance"]
        assert guidance["safety"]
        assert guidance["amenities"]
        assert guidance["transit_character"]
        assert rank["excluded"] is False
        assert rank["reason"]
        assert isinstance(rank["matched"], list)
        assert isinstance(rank["score"], (int, float))

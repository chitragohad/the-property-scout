"""API tests for listing snapshot history."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "snap.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from app.config import get_settings
    from app.db.models import Base, ListingRow
    from app.db.session import get_engine, get_session_factory, init_db, reset_engine_cache

    get_settings.cache_clear()
    reset_engine_cache()
    init_db()

    with get_session_factory()() as session:
        session.add(
            ListingRow(
                listing_id="blr-km-201",
                source_url="https://bengaluru.rent/#listing-km-201",
                location="Bengaluru",
                locality="Koramangala",
                rent=32000,
                bedrooms=2,
                furnishing="semi-furnished",
                amenities_json='["parking"]',
                society_name="Test Society",
                square_footage=1050,
                available_from="2026-07-01",
                deposit_amount=64000,
                listing_type="whole flat",
                food_preference="any",
                smoking_preference="any",
                gender=None,
                neighborhood_guidance_json="{}",
                availability_status="available",
                latitude=12.93,
                longitude=77.62,
            )
        )
        session.commit()

    # Generate snapshots into this test DB
    import sys

    root = Path(__file__).resolve().parents[3]
    ingest = root / "workers" / "ingest"
    if str(ingest) not in sys.path:
        sys.path.insert(0, str(ingest))
    from snapshots import build_snapshot_cache

    build_snapshot_cache(out_path=tmp_path / "listings.snapshots.90d.json")

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    reset_engine_cache()
    os.environ.pop("DATABASE_URL", None)


def test_get_listing_snapshots(client: TestClient):
    res = client.get("/listings/blr-km-201/snapshots")
    assert res.status_code == 200
    body = res.json()
    assert body["listing_id"] == "blr-km-201"
    assert body["days"] == 90
    assert len(body["snapshots"]) == 90
    assert body["snapshots"][-1]["as_of_date"] == "2026-08-21"
    assert body["snapshots"][-1]["rent"] == 32000
    assert body["snapshots"][-1]["availability_status"] == "available"


def test_snapshots_404(client: TestClient):
    res = client.get("/listings/missing/snapshots")
    assert res.status_code == 404


def test_unavailable_listing_snapshots_hidden(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Reuse same DB: insert a rented listing and ensure snapshots endpoint hides it
    from app.db.models import ListingRow
    from app.db.session import get_session_factory

    with get_session_factory()() as session:
        session.add(
            ListingRow(
                listing_id="blr-rented-001",
                source_url="https://bengaluru.rent/#listing-rented",
                location="Bengaluru",
                locality="Koramangala",
                rent=30000,
                bedrooms=2,
                furnishing="furnished",
                amenities_json="[]",
                society_name="Gone",
                square_footage=900,
                available_from="2026-01-01",
                deposit_amount=60000,
                listing_type="whole flat",
                food_preference="any",
                smoking_preference="any",
                gender=None,
                neighborhood_guidance_json="{}",
                availability_status="rented",
                latitude=12.93,
                longitude=77.62,
            )
        )
        session.commit()

    res = client.get("/listings/blr-rented-001/snapshots")
    assert res.status_code == 404

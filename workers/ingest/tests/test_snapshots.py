"""Tests for 90-day listing snapshot generation."""

from __future__ import annotations

from datetime import date, timedelta

from snapshots import DEFAULT_AS_OF, DEFAULT_DAYS, generate_series_for_listing


def test_series_length_and_endpoints():
    series = generate_series_for_listing(
        listing_id="blr-km-201",
        current_rent=32000,
        current_deposit=64000,
        current_status="available",
        available_from="2026-08-25",
        as_of=DEFAULT_AS_OF,
        days=DEFAULT_DAYS,
    )
    assert len(series) == 90
    assert series[0]["as_of_date"] == (DEFAULT_AS_OF - timedelta(days=89)).isoformat()
    assert series[-1]["as_of_date"] == DEFAULT_AS_OF.isoformat()
    assert series[-1]["rent"] == 32000
    assert series[-1]["deposit_amount"] == 64000
    assert series[-1]["availability_status"] == "available"
    assert all(row["availability_status"] == "available" for row in series)


def test_unavailable_listing_skipped():
    series = generate_series_for_listing(
        listing_id="blr-gone-001",
        current_rent=25000,
        current_deposit=50000,
        current_status="rented",
        available_from="2026-06-01",
        as_of=DEFAULT_AS_OF,
        days=DEFAULT_DAYS,
    )
    assert series == []


def test_series_is_deterministic():
    kwargs = dict(
        listing_id="blr-hsr-301",
        current_rent=33000,
        current_deposit=66000,
        current_status="available",
        available_from="2026-08-22",
        as_of=date(2026, 8, 21),
        days=90,
    )
    a = generate_series_for_listing(**kwargs)
    b = generate_series_for_listing(**kwargs)
    assert a == b


def test_dates_are_contiguous():
    series = generate_series_for_listing(
        listing_id="blr-ind-401",
        current_rent=38000,
        current_deposit=114000,
        current_status="available",
        available_from="2026-09-01",
        as_of=DEFAULT_AS_OF,
        days=30,
    )
    dates = [date.fromisoformat(row["as_of_date"]) for row in series]
    for i in range(1, len(dates)):
        assert dates[i] - dates[i - 1] == timedelta(days=1)


def test_export_matches_normalized_listing_fields(tmp_path):
    """Snapshot JSON listings include the same public fields as normalized export."""
    import json
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    api = root / "apps" / "api"
    if str(api) not in sys.path:
        sys.path.insert(0, str(api))

    from app.db.models import ListingRow
    from app.db.session import get_session_factory, init_db, reset_engine_cache
    from app.config import get_settings
    import os

    db_path = tmp_path / "match.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    get_settings.cache_clear()
    reset_engine_cache()
    init_db()

    with get_session_factory()() as session:
        session.add(
            ListingRow(
                listing_id="blr-hsr-301",
                source_url="https://bengaluru.rent/#listing-hsr-301",
                location="Bengaluru",
                locality="HSR Layout",
                rent=33000,
                bedrooms=2,
                furnishing="semi-furnished",
                amenities_json='["parking", "balcony"]',
                society_name="Sector 2 Greens",
                square_footage=1100,
                available_from="2026-08-22",
                deposit_amount=66000,
                listing_type="room in a flat",
                food_preference="veg",
                smoking_preference="no smoking",
                gender="male",
                neighborhood_guidance_json=json.dumps(
                    {
                        "locality": "HSR Layout",
                        "safety": "safe",
                        "amenities": "shops",
                        "transit_character": "bus",
                        "sources": [],
                    }
                ),
                availability_status="available",
                latitude=12.91,
                longitude=77.64,
            )
        )
        session.commit()

    from snapshots import build_snapshot_cache
    from export_json import export_listings

    norm_path = tmp_path / "normalized.json"
    snap_path = tmp_path / "snapshots.json"
    export_listings(out_path=norm_path)
    build_snapshot_cache(out_path=snap_path, days=5)

    normalized = json.loads(norm_path.read_text())["listings"][0]
    snapped = json.loads(snap_path.read_text())["listings"][0]

    for key, value in normalized.items():
        assert snapped[key] == value, key
    assert "snapshots" in snapped
    assert len(snapped["snapshots"]) == 5
    assert snapped["snapshots"][-1]["rent"] == snapped["rent"]

    get_settings.cache_clear()
    reset_engine_cache()
    os.environ.pop("DATABASE_URL", None)

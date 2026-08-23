"""Upsert normalized listings into the shared SQLite/Postgres database."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Allow importing sibling ingest modules and the API package
_ROOT = Path(__file__).resolve().parents[2]
_API_ROOT = _ROOT / "apps" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import get_session_factory, init_db  # noqa: E402
from app.db.models import ListingRow  # noqa: E402
from normalize import normalize_listing  # noqa: E402
from pii import assert_no_pii_keys  # noqa: E402
from scrape import load_raw_listings  # noqa: E402
from export_json import export_listings  # noqa: E402
from snapshots import build_snapshot_cache  # noqa: E402


def upsert_listings(normalized: list[dict[str, Any]]) -> int:
    """Insert or update listings. Returns count written."""
    init_db()
    session_factory = get_session_factory()
    written = 0
    with session_factory() as session:
        for item in normalized:
            assert_no_pii_keys(item)
            existing = session.get(ListingRow, item["listing_id"])
            amenities_json = json.dumps(item["amenities"])
            guidance_json = json.dumps(item["neighborhood_guidance"])
            if existing is None:
                row = ListingRow(
                    listing_id=item["listing_id"],
                    source_url=item["source_url"],
                    location=item["location"],
                    locality=item["locality"],
                    rent=item["rent"],
                    bedrooms=item["bedrooms"],
                    furnishing=item["furnishing"],
                    amenities_json=amenities_json,
                    society_name=item["society_name"],
                    square_footage=float(item["square_footage"]),
                    available_from=item["available_from"],
                    deposit_amount=int(item["deposit_amount"]),
                    listing_type=item["listing_type"],
                    food_preference=item["food_preference"],
                    smoking_preference=item["smoking_preference"],
                    gender=item.get("gender"),
                    neighborhood_guidance_json=guidance_json,
                    availability_status=item["availability_status"],
                    latitude=float(item["latitude"]),
                    longitude=float(item["longitude"]),
                )
                session.add(row)
            else:
                existing.source_url = item["source_url"]
                existing.location = item["location"]
                existing.locality = item["locality"]
                existing.rent = item["rent"]
                existing.bedrooms = item["bedrooms"]
                existing.furnishing = item["furnishing"]
                existing.amenities_json = amenities_json
                existing.society_name = item["society_name"]
                existing.square_footage = float(item["square_footage"])
                existing.available_from = item["available_from"]
                existing.deposit_amount = int(item["deposit_amount"])
                existing.listing_type = item["listing_type"]
                existing.food_preference = item["food_preference"]
                existing.smoking_preference = item["smoking_preference"]
                existing.gender = item.get("gender")
                existing.neighborhood_guidance_json = guidance_json
                existing.availability_status = item["availability_status"]
                existing.latitude = float(item["latitude"])
                existing.longitude = float(item["longitude"])
            written += 1
        session.commit()
    return written


def run_ingest(*, use_seed: bool = True) -> dict[str, int]:
    raw = load_raw_listings(use_seed=use_seed)
    normalized: list[dict[str, Any]] = []
    skipped = 0
    for item in raw:
        result = normalize_listing(item)
        if result is None:
            skipped += 1
            continue
        normalized.append(result)
    written = upsert_listings(normalized)
    return {"raw": len(raw), "written": written, "skipped": skipped}


def main() -> None:
    stats = run_ingest(use_seed=True)
    db_url = os.getenv("DATABASE_URL", "(default sqlite)")
    print(
        f"Ingest complete — raw={stats['raw']} written={stats['written']} "
        f"skipped={stats['skipped']} db={db_url}"
    )
    out = export_listings()
    print(f"Normalized JSON → {out}")
    snap = build_snapshot_cache()
    print(
        f"90-day snapshots → listings={snap['listing_count']} "
        f"rows={snap['written']} file={snap['path']}"
    )


if __name__ == "__main__":
    main()

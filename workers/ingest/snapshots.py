"""Generate and persist 90-day daily rent/availability snapshots per listing.

History is seeded (deterministic per listing_id) for demo/offline use until
live daily scrapes exist. Today's point matches the current listing row.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_API_ROOT = _ROOT / "apps" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.db.models import ListingRow, ListingSnapshotRow  # noqa: E402
from app.db.session import get_session_factory, init_db  # noqa: E402
from app.services.listing_public import listing_to_public_dict  # noqa: E402

DEFAULT_DAYS = 90
DEFAULT_OUT = _ROOT / "data" / "listings.snapshots.90d.json"
# Anchor "today" for reproducible seed history in this project
DEFAULT_AS_OF = date(2026, 8, 21)


def _rng_for(listing_id: str) -> random.Random:
    digest = hashlib.sha256(listing_id.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _round_rent(value: int) -> int:
    stepped = int(round(value / 500.0) * 500)
    return max(5000, stepped)


def generate_series_for_listing(
    *,
    listing_id: str,
    current_rent: int,
    current_deposit: int,
    current_status: str,
    available_from: str | None,
    as_of: date,
    days: int = DEFAULT_DAYS,
) -> list[dict[str, Any]]:
    """Build `days` daily points ending on `as_of` (inclusive), chronological order.

    Only available flats are snapshotted; every day in the series is marked available.
    """
    if current_status != "available":
        return []

    rng = _rng_for(listing_id)
    deposit_ratio = (current_deposit / current_rent) if current_rent else 2.0

    # Walk backward from as_of so day 0 matches the live listing exactly
    backward: list[dict[str, Any]] = []
    rent = int(current_rent)
    for days_ago in range(days):
        day = as_of - timedelta(days=days_ago)

        if days_ago == 0:
            rent_i = int(current_rent)
            deposit_i = int(current_deposit)
        else:
            # Occasional rent step when moving further into the past
            if rng.random() < 0.04:
                rent = _round_rent(rent + rng.choice([-2000, -1500, -1000, -500, 500, 1000]))
            rent_i = rent
            deposit_i = (
                int(round(rent_i * deposit_ratio / 1000.0) * 1000)
                if deposit_ratio
                else int(current_deposit)
            )

        backward.append(
            {
                "listing_id": listing_id,
                "as_of_date": day.isoformat(),
                "rent": rent_i,
                "deposit_amount": deposit_i,
                "availability_status": "available",
            }
        )

    backward.reverse()
    return backward


def generate_all_snapshots(
    *,
    as_of: date = DEFAULT_AS_OF,
    days: int = DEFAULT_DAYS,
) -> list[dict[str, Any]]:
    init_db()
    all_rows: list[dict[str, Any]] = []
    with get_session_factory()() as session:
        listings = session.scalars(
            select(ListingRow)
            .where(ListingRow.availability_status == "available")
            .order_by(ListingRow.listing_id)
        ).all()
        for row in listings:
            all_rows.extend(
                generate_series_for_listing(
                    listing_id=row.listing_id,
                    current_rent=row.rent,
                    current_deposit=row.deposit_amount,
                    current_status=row.availability_status,
                    available_from=row.available_from,
                    as_of=as_of,
                    days=days,
                )
            )
    return all_rows


def upsert_snapshots(snapshots: list[dict[str, Any]]) -> int:
    init_db()
    if not snapshots:
        return 0
    listing_ids = sorted({s["listing_id"] for s in snapshots})
    with get_session_factory()() as session:
        session.execute(
            delete(ListingSnapshotRow).where(ListingSnapshotRow.listing_id.in_(listing_ids))
        )
        for item in snapshots:
            session.add(
                ListingSnapshotRow(
                    listing_id=item["listing_id"],
                    as_of_date=item["as_of_date"],
                    rent=int(item["rent"]),
                    deposit_amount=int(item["deposit_amount"]),
                    availability_status=item["availability_status"],
                )
            )
        session.commit()
    return len(snapshots)


def export_snapshots(
    snapshots: list[dict[str, Any]],
    *,
    out_path: Path | None = None,
    as_of: date = DEFAULT_AS_OF,
    days: int = DEFAULT_DAYS,
) -> Path:
    target = out_path or DEFAULT_OUT
    target.parent.mkdir(parents=True, exist_ok=True)

    by_listing: dict[str, list[dict[str, Any]]] = {}
    for row in snapshots:
        by_listing.setdefault(row["listing_id"], []).append(
            {
                "as_of_date": row["as_of_date"],
                "rent": row["rent"],
                "deposit_amount": row["deposit_amount"],
                "availability_status": row["availability_status"],
            }
        )
    for series in by_listing.values():
        series.sort(key=lambda x: x["as_of_date"])

    # Attach the same public listing fields as listings.normalized.json
    listings_out: list[dict[str, Any]] = []
    with get_session_factory()() as session:
        rows = session.scalars(
            select(ListingRow)
            .where(
                ListingRow.availability_status == "available",
                ListingRow.listing_id.in_(sorted(by_listing.keys()) or ["__none__"]),
            )
            .order_by(ListingRow.locality, ListingRow.rent)
        ).all()
        for row in rows:
            item = listing_to_public_dict(row)
            item["snapshots"] = by_listing.get(row.listing_id, [])
            listings_out.append(item)

    payload = {
        "source": "seeded 90-day listing snapshots (available flats only)",
        "as_of": as_of.isoformat(),
        "days": days,
        "availability_filter": "available",
        "listing_count": len(listings_out),
        "snapshot_count": sum(len(item["snapshots"]) for item in listings_out),
        "listings": listings_out,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def build_snapshot_cache(
    *,
    as_of: date = DEFAULT_AS_OF,
    days: int = DEFAULT_DAYS,
    out_path: Path | None = None,
) -> dict[str, Any]:
    snapshots = generate_all_snapshots(as_of=as_of, days=days)
    written = upsert_snapshots(snapshots)
    path = export_snapshots(snapshots, out_path=out_path, as_of=as_of, days=days)
    return {
        "written": written,
        "listing_count": len({s["listing_id"] for s in snapshots}),
        "days": days,
        "as_of": as_of.isoformat(),
        "path": str(path),
    }


def main() -> None:
    stats = build_snapshot_cache()
    print(
        f"Snapshot cache — listings={stats['listing_count']} "
        f"days={stats['days']} rows={stats['written']} as_of={stats['as_of']}"
    )
    print(f"Wrote → {stats['path']}")


if __name__ == "__main__":
    main()

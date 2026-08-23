"""Export scrubbed/normalized listings from the DB to JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_API_ROOT = _ROOT / "apps" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.models import ListingRow  # noqa: E402
from app.db.session import get_session_factory, init_db  # noqa: E402
from app.services.listing_public import listing_to_public_dict  # noqa: E402

DEFAULT_OUT = _ROOT / "data" / "listings.normalized.json"


def export_listings(out_path: Path | None = None) -> Path:
    target = out_path or DEFAULT_OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    init_db()

    listings = []
    with get_session_factory()() as session:
        rows = session.scalars(
            select(ListingRow)
            .where(ListingRow.availability_status == "available")
            .order_by(ListingRow.locality, ListingRow.rent)
        ).all()
        listings = [listing_to_public_dict(row) for row in rows]

    payload = {
        "source": "bengaluru.rent (scrubbed/normalized ingest)",
        "count": len(listings),
        "listings": listings,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def main() -> None:
    path = export_listings()
    print(f"Wrote normalized listings → {path}")


if __name__ == "__main__":
    main()

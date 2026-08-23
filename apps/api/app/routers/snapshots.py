"""Listing snapshot history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ListingRow, ListingSnapshotRow
from app.db.session import get_db
from app.schemas.snapshot import ListingDaySnapshot, ListingSnapshotSeries

router = APIRouter(prefix="/listings", tags=["snapshots"])


@router.get("/{listing_id}/snapshots", response_model=ListingSnapshotSeries)
def get_listing_snapshots(
    listing_id: str,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> ListingSnapshotSeries:
    listing = db.get(ListingRow, listing_id)
    if listing is None or listing.availability_status != "available":
        raise HTTPException(status_code=404, detail="Listing not found")

    rows = db.scalars(
        select(ListingSnapshotRow)
        .where(
            ListingSnapshotRow.listing_id == listing_id,
            ListingSnapshotRow.availability_status == "available",
        )
        .order_by(ListingSnapshotRow.as_of_date.desc())
        .limit(days)
    ).all()
    # Return chronological
    rows = list(reversed(rows))
    snapshots = [
        ListingDaySnapshot(
            listing_id=row.listing_id,
            as_of_date=row.as_of_date,
            rent=row.rent,
            deposit_amount=row.deposit_amount,
            availability_status=row.availability_status,
        )
        for row in rows
    ]
    return ListingSnapshotSeries(
        listing_id=listing_id,
        days=len(snapshots),
        snapshots=snapshots,
    )

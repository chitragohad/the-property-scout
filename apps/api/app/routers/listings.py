from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import ListingRow
from app.db.session import get_db
from app.schemas.constraints import HardConstraints
from app.schemas.listing import Listing
from app.services.retrieval import find_candidates, row_to_listing

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=list[Listing], response_model_exclude_none=True)
def list_candidates(
    bedrooms: int | None = Query(default=None, ge=0),
    locality: str | None = Query(default=None),
    max_rent: int | None = Query(default=None, ge=0),
    must_have: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[Listing]:
    constraints = HardConstraints(
        bedrooms=bedrooms,
        locality=locality,
        max_rent=max_rent,
        must_have_amenities=must_have or [],
    )
    return find_candidates(db, constraints, limit=limit)


@router.get("/{listing_id}", response_model=Listing, response_model_exclude_none=True)
def get_listing(listing_id: str, db: Session = Depends(get_db)) -> Listing:
    row = db.get(ListingRow, listing_id)
    if row is None or row.availability_status != "available":
        raise HTTPException(status_code=404, detail="Listing not found")
    return row_to_listing(row)

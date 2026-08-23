"""Property retrieval by hard constraints."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ListingRow
from app.schemas.constraints import HardConstraints
from app.schemas.listing import Listing, NeighborhoodGuidance


def row_to_listing(row: ListingRow) -> Listing:
    return Listing(
        listing_id=row.listing_id,
        source_url=row.source_url,
        location=row.location,
        locality=row.locality,
        rent=row.rent,
        bedrooms=row.bedrooms,
        furnishing=row.furnishing,
        amenities=row.amenities(),
        society_name=row.society_name,
        square_footage=row.square_footage,
        available_from=row.available_from,
        deposit_amount=row.deposit_amount,
        listing_type=row.listing_type,
        food_preference=row.food_preference,
        smoking_preference=row.smoking_preference,
        gender=row.gender,
        neighborhood_guidance=NeighborhoodGuidance.model_validate(
            row.neighborhood_guidance()
        ),
        availability_status=row.availability_status,
        latitude=row.latitude,
        longitude=row.longitude,
    )


def _locality_matches(listing_locality: str, wanted: str) -> bool:
    left = listing_locality.strip().lower()
    right = wanted.strip().lower()
    return left == right or right in left or left in right


def find_candidates(
    session: Session,
    constraints: HardConstraints,
    limit: int = 50,
) -> list[Listing]:
    """Return available listings matching hard constraints."""
    stmt = select(ListingRow).where(ListingRow.availability_status == "available")

    if constraints.bedrooms is not None:
        stmt = stmt.where(ListingRow.bedrooms == constraints.bedrooms)
    if constraints.max_rent is not None:
        stmt = stmt.where(ListingRow.rent <= constraints.max_rent)

    # Locality and amenities filtered in Python for flexible matching / JSON amenities
    rows = session.scalars(stmt).all()
    results: list[Listing] = []
    must_haves = [a.strip().lower() for a in constraints.must_have_amenities if a.strip()]

    for row in rows:
        if constraints.locality and not _locality_matches(row.locality, constraints.locality):
            continue
        amenities = {a.strip().lower() for a in row.amenities()}
        if must_haves and not all(req in amenities for req in must_haves):
            continue
        results.append(row_to_listing(row))
        if len(results) >= limit:
            break

    return results

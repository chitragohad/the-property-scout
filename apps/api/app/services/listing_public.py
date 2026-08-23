"""Shared public listing shape for normalized JSON exports."""

from __future__ import annotations

from typing import Any

from app.db.models import ListingRow


def listing_to_public_dict(row: ListingRow) -> dict[str, Any]:
    """Normalized public view: available listings; no geo or status fields."""
    item: dict[str, Any] = {
        "listing_id": row.listing_id,
        "source_url": row.source_url,
        "location": row.location,
        "locality": row.locality,
        "rent": row.rent,
        "bedrooms": row.bedrooms,
        "furnishing": row.furnishing,
        "amenities": row.amenities(),
        "society_name": row.society_name,
        "square_footage": row.square_footage,
        "available_from": row.available_from,
        "deposit_amount": row.deposit_amount,
        "listing_type": row.listing_type,
        "food_preference": row.food_preference,
        "smoking_preference": row.smoking_preference,
        "neighborhood_guidance": row.neighborhood_guidance(),
    }
    if row.listing_type == "room in a flat" and row.gender:
        item["gender"] = row.gender
    return item

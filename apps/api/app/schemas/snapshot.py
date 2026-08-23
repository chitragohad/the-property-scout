from pydantic import BaseModel, Field


class ListingDaySnapshot(BaseModel):
    listing_id: str
    as_of_date: str  # YYYY-MM-DD
    rent: int = Field(..., ge=0)
    deposit_amount: int = Field(..., ge=0)
    availability_status: str


class ListingSnapshotSeries(BaseModel):
    listing_id: str
    days: int
    snapshots: list[ListingDaySnapshot]

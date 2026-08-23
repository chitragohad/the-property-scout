from pydantic import BaseModel, Field, HttpUrl


class NeighborhoodSource(BaseModel):
    title: str
    url: str
    snippet: str = ""


class NeighborhoodGuidance(BaseModel):
    """Practical locality guidance attached to a listing."""

    locality: str
    safety: str
    amenities: str
    transit_character: str
    sources: list[NeighborhoodSource] = Field(default_factory=list)


class Listing(BaseModel):
    listing_id: str
    source_url: HttpUrl | str
    location: str
    locality: str
    rent: int = Field(..., ge=0)
    bedrooms: int = Field(..., ge=0)
    furnishing: str
    amenities: list[str]
    society_name: str
    square_footage: float | int = Field(..., ge=0)
    available_from: str  # ISO date YYYY-MM-DD — flat available from this date
    deposit_amount: int = Field(..., ge=0)  # security deposit in INR
    listing_type: str  # "whole flat" | "room in a flat"
    food_preference: str  # veg | non-veg | any
    smoking_preference: str  # no smoking | smoking allowed | any
    gender: str | None = None  # male | female | any — only for "room in a flat"
    neighborhood_guidance: NeighborhoodGuidance
    availability_status: str
    latitude: float
    longitude: float

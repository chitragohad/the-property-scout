from typing import Literal

from pydantic import BaseModel, Field


class HardConstraints(BaseModel):
    bedrooms: int | None = None
    locality: str | None = None
    max_rent: int | None = None
    must_have_amenities: list[str] = Field(default_factory=list)


class SoftPreferences(BaseModel):
    near_metro: bool | None = None
    pet_friendly: bool | None = None
    balcony: bool | None = None


class Constraints(BaseModel):
    hard: HardConstraints = Field(default_factory=HardConstraints)
    soft: SoftPreferences = Field(default_factory=SoftPreferences)
    commute_point: str | None = None


class PreferencePatch(BaseModel):
    hard: HardConstraints | None = None
    soft: SoftPreferences | None = None
    commute_point: str | None = None
    patch_mode: Literal["merge"] = "merge"

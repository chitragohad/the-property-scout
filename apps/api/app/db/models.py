from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ListingRow(Base):
    __tablename__ = "listings"

    listing_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    locality: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rent: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bedrooms: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    furnishing: Mapped[str] = mapped_column(String(64), nullable=False)
    amenities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    society_name: Mapped[str] = mapped_column(String(255), nullable=False)
    square_footage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    available_from: Mapped[str] = mapped_column(String(32), nullable=False, default="2026-08-21")
    deposit_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    listing_type: Mapped[str] = mapped_column(String(64), nullable=False, default="whole flat")
    food_preference: Mapped[str] = mapped_column(String(32), nullable=False, default="any")
    smoking_preference: Mapped[str] = mapped_column(String(32), nullable=False, default="any")
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    neighborhood_guidance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    availability_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def amenities(self) -> list[str]:
        try:
            value = json.loads(self.amenities_json or "[]")
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []

    def neighborhood_guidance(self) -> dict:
        try:
            value = json.loads(self.neighborhood_guidance_json or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


class ListingSnapshotRow(Base):
    """Daily rent / availability point-in-time snapshot for a listing."""

    __tablename__ = "listing_snapshots"
    __table_args__ = (
        UniqueConstraint("listing_id", "as_of_date", name="uq_listing_snapshot_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("listings.listing_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    as_of_date: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # YYYY-MM-DD
    rent: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    availability_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

"""OSM enrichment schemas (Overpass / MCP-shaped)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OsmPoi(BaseModel):
    name: str
    category: str  # metro|transit|restaurant|school|hospital|grocery|park|other
    lat: float
    lon: float
    distance_m: float | None = None


class OsmContext(BaseModel):
    listing_id: str
    pois: list[OsmPoi] = Field(default_factory=list)
    raw_call_id: str
    empty_reason: str | None = None


class NeighborhoodNote(BaseModel):
    """Cited neighborhood prose attached to a shortlist card."""

    topic: str
    text: str
    citation_id: str

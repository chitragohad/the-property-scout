"""OSM enrichment service with (listing_id, radius_m) cache."""

from __future__ import annotations

from app.schemas.listing import Listing
from app.schemas.osm import OsmContext
from app.services.osm_client import OsmNearbyClient, OverpassOsmClient, StaticOsmClient
from app.services.ranking import Enrichment

_DEFAULT_RADIUS = 800


def _default_client() -> OsmNearbyClient:
    from app.config import get_settings

    if get_settings().osm_mode.lower() in {"static"}:
        return StaticOsmClient()
    return OverpassOsmClient()


class OsmService:
    def __init__(self, client: OsmNearbyClient | None = None) -> None:
        self._client: OsmNearbyClient = client or _default_client()
        self._cache: dict[tuple[str, int], OsmContext] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def nearby_for_listing(
        self,
        listing: Listing,
        *,
        radius_m: int = _DEFAULT_RADIUS,
    ) -> OsmContext:
        key = (listing.listing_id, radius_m)
        if key in self._cache:
            return self._cache[key]
        ctx = self._client.nearby(
            listing_id=listing.listing_id,
            lat=listing.latitude,
            lon=listing.longitude,
            radius_m=radius_m,
        )
        self._cache[key] = ctx
        return ctx

    def enrichment_from_context(self, ctx: OsmContext) -> Enrichment:
        transitish = [p for p in ctx.pois if p.category in {"metro", "transit"}]
        has_metro = any(p.category == "metro" for p in ctx.pois)
        if ctx.pois:
            near_metro: bool | None = has_metro
        else:
            near_metro = None  # unverified — do not invent absence as fact beyond empty_reason

        notes: list[str] = []
        if ctx.empty_reason:
            notes.append(ctx.empty_reason)
        elif transitish:
            closest = min(transitish, key=lambda p: p.distance_m or 1e9)
            notes.append(
                f"Nearest {closest.category}: {closest.name} (~{int(closest.distance_m or 0)}m)"
            )
        return Enrichment(
            listing_id=ctx.listing_id,
            near_metro=near_metro,
            transit_poi_count=len(transitish),
            notes=notes,
        )

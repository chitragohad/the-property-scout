"""OSM Overpass client (MCP-shaped wrapper for nearby POIs).

Uses the public Overpass API so enrichment works without a separate MCP
process. The interface mirrors the Phase 3 plan (`raw_call_id`, empty_reason).
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Protocol

from app.schemas.osm import OsmContext, OsmPoi

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# amenity/railway/leisure tags → product categories
_TAG_CATEGORY: list[tuple[str, str, str]] = [
    # (key, value, category)
    ("railway", "station", "metro"),
    ("railway", "subway_entrance", "metro"),
    ("station", "subway", "metro"),
    ("public_transport", "station", "transit"),
    ("highway", "bus_stop", "transit"),
    ("amenity", "bus_station", "transit"),
    ("amenity", "restaurant", "restaurant"),
    ("amenity", "cafe", "restaurant"),
    ("amenity", "fast_food", "restaurant"),
    ("amenity", "school", "school"),
    ("amenity", "college", "school"),
    ("amenity", "university", "school"),
    ("amenity", "hospital", "hospital"),
    ("amenity", "clinic", "hospital"),
    ("amenity", "doctors", "hospital"),
    ("shop", "supermarket", "grocery"),
    ("shop", "convenience", "grocery"),
    ("amenity", "marketplace", "grocery"),
    ("leisure", "park", "park"),
    ("leisure", "garden", "park"),
]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _classify(tags: dict[str, str]) -> str:
    for key, value, category in _TAG_CATEGORY:
        if tags.get(key) == value:
            return category
    if tags.get("railway") in {"halt", "tram_stop"}:
        return "transit"
    if tags.get("amenity"):
        return "other"
    if tags.get("shop"):
        return "other"
    return "other"


def _poi_name(tags: dict[str, str], category: str) -> str:
    return tags.get("name") or tags.get("name:en") or f"Unnamed {category}"


class OsmNearbyClient(Protocol):
    def nearby(
        self,
        *,
        listing_id: str,
        lat: float,
        lon: float,
        radius_m: int = 800,
    ) -> OsmContext: ...


class OverpassOsmClient:
    """Fetch nearby POIs via Overpass QL."""

    def __init__(self, endpoint: str = OVERPASS_URL, timeout_s: float = 25.0) -> None:
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    def _build_query(self, lat: float, lon: float, radius_m: int) -> str:
        # Keep query compact: common residential amenities + transit
        filters = [
            'node["railway"~"station|subway_entrance"]',
            'node["public_transport"="station"]',
            'node["highway"="bus_stop"]',
            'node["amenity"~"restaurant|cafe|school|hospital|clinic|bus_station"]',
            'node["shop"~"supermarket|convenience"]',
            'node["leisure"="park"]',
        ]
        parts = [f"{f}(around:{radius_m},{lat},{lon});" for f in filters]
        return f"[out:json][timeout:25];({''.join(parts)});out body center;"

    def _http_post(self, query: str) -> dict[str, Any]:
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def nearby(
        self,
        *,
        listing_id: str,
        lat: float,
        lon: float,
        radius_m: int = 800,
    ) -> OsmContext:
        call_id = f"overpass-{uuid.uuid4().hex[:12]}"
        try:
            payload = self._http_post(self._build_query(lat, lon, radius_m))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return OsmContext(
                listing_id=listing_id,
                pois=[],
                raw_call_id=call_id,
                empty_reason=(
                    "Could not query OpenStreetMap Overpass for nearby POIs "
                    f"({type(exc).__name__})."
                ),
            )

        elements = payload.get("elements") or []
        pois: list[OsmPoi] = []
        for el in elements:
            tags = el.get("tags") or {}
            if not isinstance(tags, dict):
                continue
            plat = el.get("lat")
            plon = el.get("lon")
            if plat is None or plon is None:
                center = el.get("center") or {}
                plat = center.get("lat")
                plon = center.get("lon")
            if plat is None or plon is None:
                continue
            category = _classify({str(k): str(v) for k, v in tags.items()})
            dist = haversine_m(lat, lon, float(plat), float(plon))
            if dist > radius_m * 1.05:
                continue
            pois.append(
                OsmPoi(
                    name=_poi_name({str(k): str(v) for k, v in tags.items()}, category),
                    category=category,
                    lat=float(plat),
                    lon=float(plon),
                    distance_m=round(dist, 1),
                )
            )

        # Prefer closer POIs; cap for shortlist payload size
        pois.sort(key=lambda p: p.distance_m or 1e9)
        pois = pois[:25]

        if not pois:
            return OsmContext(
                listing_id=listing_id,
                pois=[],
                raw_call_id=call_id,
                empty_reason=(
                    "Couldn't find nearby transit/POI in available OpenStreetMap data "
                    f"within {radius_m}m."
                ),
            )
        return OsmContext(listing_id=listing_id, pois=pois, raw_call_id=call_id, empty_reason=None)


class StaticOsmClient:
    """Deterministic client for unit tests and OSM_MODE=static dev."""

    def __init__(self, contexts: dict[str, OsmContext] | None = None) -> None:
        self.contexts = contexts or {}

    def nearby(
        self,
        *,
        listing_id: str,
        lat: float,
        lon: float,
        radius_m: int = 800,
    ) -> OsmContext:
        if listing_id in self.contexts:
            return self.contexts[listing_id]
        return _synthetic_osm_context(listing_id, lat, lon, radius_m)


def _synthetic_osm_context(
    listing_id: str,
    lat: float,
    lon: float,
    radius_m: int,
) -> OsmContext:
    """Coordinate-seeded POIs so each listing pin differs in static/dev mode."""
    import hashlib

    seed = int(hashlib.sha256(f"{listing_id}:{lat:.6f}:{lon:.6f}".encode()).hexdigest()[:8], 16)

    def _dist(offset: int) -> float:
        return float(120 + ((seed >> offset) % 550))

    metro_dist = _dist(0)
    grocery_dist = _dist(4)
    bus_dist = _dist(8)
    park_dist = _dist(12)

    pois = [
        OsmPoi(
            name="Koramangala Metro" if "km" in listing_id else f"Transit Hub {listing_id[-3:]}",
            category="metro",
            lat=lat + 0.001,
            lon=lon + 0.001,
            distance_m=metro_dist,
        ),
        OsmPoi(
            name=f"Corner Store {listing_id[-3:]}",
            category="grocery",
            lat=lat - 0.0008,
            lon=lon + 0.0006,
            distance_m=grocery_dist,
        ),
        OsmPoi(
            name=f"Bus Stop {listing_id[-3:]}",
            category="transit",
            lat=lat + 0.0005,
            lon=lon - 0.0007,
            distance_m=bus_dist,
        ),
        OsmPoi(
            name="Neighbourhood Park",
            category="park",
            lat=lat - 0.0012,
            lon=lon - 0.0005,
            distance_m=park_dist,
        ),
    ]
    pois.sort(key=lambda p: p.distance_m or 1e9)
    return OsmContext(
        listing_id=listing_id,
        pois=pois,
        raw_call_id=f"static-synthetic-{listing_id}",
        empty_reason=None,
    )

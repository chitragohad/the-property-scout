"""Locality-level practical neighborhood guidance for listings.

Seeded from public neighborhood character notes. Phase 3 enriches via RAG + OSM;
guidance is locality-keyed and attached at normalize time — never invented per-listing POIs.
"""

from __future__ import annotations

from typing import Any

BENGALURU_RENT_SOURCE: dict[str, str] = {
    "title": "bengaluru.rent",
    "url": "https://bengaluru.rent/",
    "snippet": "Public rental listings map for Bengaluru.",
}

OSM_SOURCE: dict[str, str] = {
    "title": "OpenStreetMap",
    "url": "https://www.openstreetmap.org/copyright",
    "snippet": "Open map data for transit and amenities near listings.",
}

_LOCALITY_SOURCES = [BENGALURU_RENT_SOURCE, OSM_SOURCE]

# Keys are lowercase locality names
NEIGHBORHOOD_GUIDANCE: dict[str, dict[str, Any]] = {
    "koramangala": {
        "safety": (
            "Generally regarded as a busy, well-lit residential-commercial mixed area with "
            "steady evening footfall around cafes and retail strips. As with any dense Bengaluru "
            "neighbourhood, check building security and late-night last-mile options for your block."
        ),
        "amenities": (
            "Strong everyday amenity coverage: grocery and convenience retail, cafes, gyms, "
            "clinics, and schools within short travel of most residential pockets. Forum and "
            "Sony Signal areas are common amenity anchors."
        ),
        "transit_character": (
            "Well connected by arterial roads (80 Feet / 100 Feet Road) with frequent bus "
            "coverage and growing metro access via nearby Purple Line catchments. Commute times "
            "vary sharply with peak traffic toward Outer Ring Road and CBD."
        ),
        "sources": list(_LOCALITY_SOURCES),
    },
    "hsr layout": {
        "safety": (
            "Planned sector layout with comparatively organised streets and active residential "
            "associations in many blocks. Main roads stay active into the evening; quieter "
            "interior lanes vary by sector — prefer well-reviewed societies when possible."
        ),
        "amenities": (
            "Good density of groceries, pharmacies, cafes, and coworking options especially "
            "along 27th Main and Sector 6/7 commercial stretches. Parks and playgrounds are "
            "part of the planned layout character."
        ),
        "transit_character": (
            "Strong bus connectivity and ORR access for IT corridor commuting. Metro coverage "
            "is improving via nearby corridors; last-mile often relies on autos/cabs within sectors."
        ),
        "sources": list(_LOCALITY_SOURCES),
    },
    "indiranagar": {
        "safety": (
            "Popular, high-activity neighbourhood with nightlife and retail corridors that stay "
            "busy late. Standard urban precautions apply around crowded 100 Feet Road stretches."
        ),
        "amenities": (
            "Excellent amenity depth: restaurants, boutiques, groceries, fitness studios, and "
            "healthcare options are concentrated around 100 Feet Road and surrounding cross streets."
        ),
        "transit_character": (
            "Purple Line metro access via Indiranagar / Halasuru catchments plus dense bus and "
            "auto availability. Road congestion on 100 Feet Road is a defining commute factor."
        ),
        "sources": list(_LOCALITY_SOURCES),
    },
    "whitefield": {
        "safety": (
            "Large IT-residential belt with gated communities and busy commercial nodes. "
            "Safety perception is generally tied to society security and main-road lighting; "
            "verify last-mile access for specific campuses or back lanes."
        ),
        "amenities": (
            "Malls, hypermarkets, hospitals, and schools serve the wider Whitefield catchment. "
            "Amenity quality is strong near ITPL / Hope Farm / Varthur Road corridors."
        ),
        "transit_character": (
            "Historically road-heavy commuting with Namma Metro Purple Line extension improving "
            "rail options. Peak-hour ORR and Whitefield Main Road delays remain common."
        ),
        "sources": list(_LOCALITY_SOURCES),
    },
    "jayanagar": {
        "safety": (
            "Established residential locality with family-oriented streets and active local "
            "commerce. Generally considered calm relative to nightlife districts; still confirm "
            "building-level security for ground-floor or older walk-ups."
        ),
        "amenities": (
            "Mature amenity ecosystem: markets, temples, parks (including Cubbon Park proximity "
            "trade-offs by block), clinics, and traditional retail around 4th Block and nearby circles."
        ),
        "transit_character": (
            "Good bus connectivity toward south and central Bengaluru; metro access via nearby "
            "Green/Purple catchments depending on exact block. Walkability is a relative strength "
            "in core Jayanagar grids."
        ),
        "sources": list(_LOCALITY_SOURCES),
    },
}

_DEFAULT_GUIDANCE: dict[str, Any] = {
    "safety": (
        "I couldn't find detailed locality-specific public safety notes beyond general "
        "Bengaluru urban guidance. Verify society security, street lighting, and late-night "
        "transit for this exact pin."
    ),
    "amenities": (
        "Local amenity mix varies by micro-pocket. Confirm groceries, healthcare, and daily "
        "needs against OpenStreetMap / on-ground checks for this listing's coordinates."
    ),
    "transit_character": (
        "Transit character for this locality is not fully documented in the current guidance "
        "index. Prefer OpenStreetMap nearby transit queries and live commute trials."
    ),
    "sources": [],
}


def guidance_for_locality(locality: str) -> dict[str, Any]:
    key = locality.strip().lower()
    # Exact then fuzzy contains
    if key in NEIGHBORHOOD_GUIDANCE:
        base = NEIGHBORHOOD_GUIDANCE[key]
    else:
        base = next(
            (v for k, v in NEIGHBORHOOD_GUIDANCE.items() if k in key or key in k),
            _DEFAULT_GUIDANCE,
        )
    return {
        "locality": locality,
        "safety": base["safety"],
        "amenities": base["amenities"],
        "transit_character": base["transit_character"],
        "sources": list(base.get("sources") or []),
    }

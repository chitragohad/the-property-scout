"""Display citations for shortlist cards and the Sources panel."""

from __future__ import annotations

from app.schemas.listing import Listing
from app.schemas.osm import OsmContext
from app.schemas.ranking import Citation


def osm_map_url(lat: float, lon: float, *, zoom: int = 16) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map={zoom}/{lat}/{lon}"


def is_wikipedia_url(url: str) -> bool:
    return "wikipedia.org" in url.lower()


def build_listing_source_citation(listing: Listing) -> Citation | None:
    url = str(listing.source_url or "").strip()
    if not url:
        return None
    rent_inr = f"₹{listing.rent:,}" if listing.rent else "rent details"
    snippet = (
        f"Listing on bengaluru.rent — {listing.locality}, "
        f"{listing.bedrooms} BHK, {rent_inr}/month."
    )
    return Citation(
        id=f"listing-{listing.listing_id}",
        title="bengaluru.rent — listing",
        url=url,
        snippet=snippet,
        locality=listing.locality,
        topic="listing",
    )


def build_osm_citation(listing: Listing, ctx: OsmContext | None) -> Citation | None:
    if ctx is None:
        return None
    poi_count = len(ctx.pois)
    if poi_count:
        snippet = f"{poi_count} nearby POIs from OpenStreetMap (transit, amenities, and more)."
    elif ctx.empty_reason:
        snippet = ctx.empty_reason
    else:
        snippet = "OpenStreetMap data for transit and amenities near this listing."
    return Citation(
        id=f"osm-{ctx.raw_call_id}",
        title="OpenStreetMap — nearby POIs",
        url=osm_map_url(listing.latitude, listing.longitude),
        snippet=snippet,
        locality=listing.locality,
        topic="osm",
    )


def display_citations_for_listing(
    rag_citations: list[Citation],
    listing: Listing,
    osm_ctx: OsmContext | None,
) -> list[Citation]:
    """Sources panel citations: bengaluru.rent listing + OSM; no Wikipedia RAG chunks."""
    cites: list[Citation] = []
    listing_cite = build_listing_source_citation(listing)
    if listing_cite:
        cites.append(listing_cite)
    osm_cite = build_osm_citation(listing, osm_ctx)
    if osm_cite:
        cites.append(osm_cite)
    if cites:
        return cites
    return _dedupe_citations_by_url(
        [c for c in rag_citations if c.id != "unverified" and not is_wikipedia_url(c.url)],
    )


def _dedupe_citations_by_url(citations: list[Citation]) -> list[Citation]:
    seen: dict[str, Citation] = {}
    for cite in citations:
        if not cite.url or cite.url in seen:
            continue
        seen[cite.url] = cite
    return list(seen.values())

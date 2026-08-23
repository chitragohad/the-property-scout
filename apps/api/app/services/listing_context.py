"""Per-listing contextual copy from bengaluru.rent fields + OSM enrichment."""

from __future__ import annotations

from app.schemas.listing import Listing
from app.schemas.osm import NeighborhoodNote, OsmContext, OsmPoi
from app.schemas.ranking import RankResult
from app.services.ranking import Enrichment


def _summarize(text: str, max_len: int = 140) -> str:
    trimmed = text.strip()
    if len(trimmed) <= max_len:
        return trimmed
    cut = trimmed[:max_len]
    last_space = cut.rfind(" ")
    base = cut[:last_space] if last_space > 40 else cut
    return f"{base}…"


def _format_poi(poi: OsmPoi) -> str:
    dist = f" (~{int(poi.distance_m or 0)}m)" if poi.distance_m is not None else ""
    name = poi.name if poi.name and not poi.name.lower().startswith("unnamed") else poi.category
    return f"{poi.category} {name}{dist}"


def _locality_note(notes: list[NeighborhoodNote], topic: str) -> NeighborhoodNote | None:
    return next((n for n in notes if n.topic == topic), None)


def build_listing_reason(
    listing: Listing,
    rank: RankResult,
    enrichment: Enrichment | None,
) -> str:
    """Grounded, listing-specific recommendation reason."""
    parts: list[str] = [
        (
            f"{listing.society_name} is a {listing.bedrooms}BHK "
            f"({int(listing.square_footage)} sq ft, {listing.furnishing}) "
            f"at ₹{listing.rent:,}/mo in {listing.locality}."
        ),
    ]

    if listing.amenities:
        parts.append(f"Listing amenities: {', '.join(listing.amenities)}.")

    if listing.deposit_amount:
        parts.append(f"Deposit ₹{listing.deposit_amount:,}; available from {listing.available_from}.")

    if rank.matched:
        parts.append(f"Matched your criteria: {', '.join(rank.matched)}.")

    if enrichment and enrichment.notes:
        parts.append(enrichment.notes[0] + ".")

    if rank.missing:
        parts.append(f"Soft gaps: {', '.join(rank.missing)}.")

    return " ".join(parts)


def build_listing_neighborhood_notes(
    listing: Listing,
    osm: OsmContext | None,
    locality_notes: list[NeighborhoodNote],
    enrichment: Enrichment | None,
) -> list[NeighborhoodNote]:
    """Merge listing fields + OSM POIs; locality RAG only where listing data is thin."""
    notes: list[NeighborhoodNote] = []
    guidance = listing.neighborhood_guidance

    safety_rag = _locality_note(locality_notes, "safety")
    safety_text = (
        f"At {listing.society_name}: verify society security and access. "
        f"Area: {_summarize(safety_rag.text if safety_rag else guidance.safety, 100)}"
    )
    notes.append(
        NeighborhoodNote(
            topic="safety",
            text=safety_text,
            citation_id=safety_rag.citation_id if safety_rag else "listing-guidance",
        )
    )

    transit_rag = _locality_note(locality_notes, "transit")
    transit_parts: list[str] = []
    if osm and osm.pois:
        transit_pois = [p for p in osm.pois if p.category in {"metro", "transit"}][:2]
        transit_parts.extend(_format_poi(p) for p in transit_pois)
    if enrichment and enrichment.notes:
        transit_parts.extend(enrichment.notes)
    if transit_parts:
        transit_text = f"From this pin: {'; '.join(transit_parts)}."
        transit_cite = "osm"
    else:
        transit_text = _summarize(
            transit_rag.text if transit_rag else guidance.transit_character,
            140,
        )
        transit_cite = transit_rag.citation_id if transit_rag else "listing-guidance"
    notes.append(
        NeighborhoodNote(
            topic="transit",
            text=transit_text,
            citation_id=transit_cite,
        )
    )

    amenity_bits: list[str] = []
    if listing.amenities:
        amenity_bits.append(f"Society/listing: {', '.join(listing.amenities)}")
    amenity_bits.append(f"{listing.listing_type}, {listing.furnishing}")
    if osm and osm.pois:
        nearby = [
            p
            for p in osm.pois
            if p.category in {"grocery", "restaurant", "park", "school", "hospital"}
        ][:3]
        if nearby:
            amenity_bits.append("Nearby: " + ", ".join(_format_poi(p) for p in nearby))
    else:
        amenities_rag = _locality_note(locality_notes, "amenities")
        amenity_bits.append(
            _summarize(amenities_rag.text if amenities_rag else guidance.amenities, 100)
        )
    notes.append(
        NeighborhoodNote(
            topic="amenities",
            text=". ".join(amenity_bits) + ".",
            citation_id="listing+osm" if osm and osm.pois else "listing",
        )
    )

    return notes


def build_poi_summary(osm: OsmContext | None) -> str | None:
    if not osm or not osm.pois:
        return None
    picked: list[OsmPoi] = []
    for category in ("metro", "grocery", "transit", "park", "restaurant"):
        poi = next((p for p in osm.pois if p.category == category), None)
        if poi and poi not in picked:
            picked.append(poi)
    for poi in osm.pois:
        if len(picked) >= 4:
            break
        if poi not in picked:
            picked.append(poi)
    if not picked:
        return None
    return ", ".join(_format_poi(p) for p in picked)

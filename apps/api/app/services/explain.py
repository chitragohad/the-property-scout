"""Grounded explanation generator — only listing/rank/OSM/RAG evidence."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.osm import OsmContext
from app.schemas.ranking import Citation, RankResult
from app.schemas.session import ShortlistItem
from app.services.gemini import GeminiClient
from app.services.rag import UNVERIFIABLE


class EvidenceBundle(BaseModel):
    listing_id: str
    society_name: str
    locality: str
    rent: int
    bedrooms: int
    amenities: list[str] = Field(default_factory=list)
    rank: RankResult
    osm_notes: list[str] = Field(default_factory=list)
    osm_poi_summaries: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    neighborhood_snippets: list[str] = Field(default_factory=list)


def build_evidence(item: ShortlistItem) -> EvidenceBundle:
    osm: OsmContext | None = item.osm
    osm_notes = []
    poi_summaries = []
    if osm:
        if osm.empty_reason:
            osm_notes.append(osm.empty_reason)
        for poi in osm.pois[:5]:
            dist = f" (~{int(poi.distance_m)}m)" if poi.distance_m is not None else ""
            poi_summaries.append(f"{poi.category}: {poi.name}{dist}")
    snippets = [n.text for n in item.neighborhood_notes if n.citation_id != "unverified"]
    unverifiable = any(n.citation_id == "unverified" for n in item.neighborhood_notes)
    if unverifiable and not snippets:
        snippets = [UNVERIFIABLE]
    return EvidenceBundle(
        listing_id=item.listing.listing_id,
        society_name=item.listing.society_name,
        locality=item.listing.locality,
        rent=item.listing.rent,
        bedrooms=item.listing.bedrooms,
        amenities=list(item.listing.amenities),
        rank=item.rank,
        osm_notes=osm_notes,
        osm_poi_summaries=poi_summaries,
        citation_ids=[c.id for c in item.citations],
        neighborhood_snippets=snippets,
    )


def explain_from_evidence(bundle: EvidenceBundle, *, question: str = "why") -> str:
    """Deterministic grounded prose (CI-safe). Gemini optional polish only."""
    q = question.lower()
    if "neighborhood" in q or "neighbourhood" in q or "area" in q:
        if not bundle.neighborhood_snippets or bundle.neighborhood_snippets == [UNVERIFIABLE]:
            return UNVERIFIABLE
        cite = f" Sources: {', '.join(bundle.citation_ids)}." if bundle.citation_ids else ""
        return f"{bundle.neighborhood_snippets[0]}{cite}"

    parts = [
        f"{bundle.society_name} in {bundle.locality} is a {bundle.bedrooms}BHK at ₹{bundle.rent}.",
        f"Match score {bundle.rank.score}: {bundle.rank.reason}",
    ]
    if bundle.rank.matched:
        parts.append(f"Matched: {', '.join(bundle.rank.matched)}.")
    if bundle.rank.missing:
        parts.append(f"Soft gaps: {', '.join(bundle.rank.missing)}.")
    if bundle.osm_poi_summaries:
        parts.append("Nearby OpenStreetMap POIs: " + "; ".join(bundle.osm_poi_summaries[:3]) + ".")
    elif bundle.osm_notes:
        parts.append(bundle.osm_notes[0])
    if bundle.neighborhood_snippets and bundle.neighborhood_snippets != [UNVERIFIABLE]:
        parts.append(f"Neighborhood note: {bundle.neighborhood_snippets[0][:220]}")
        if bundle.citation_ids:
            parts.append(f"(citations: {', '.join(bundle.citation_ids[:3])})")
    elif "neighborhood" in q:
        return UNVERIFIABLE
    return " ".join(parts)


def explain_why_not(excluded_reason: RankResult) -> str:
    reasons = excluded_reason.exclusion_reasons or [excluded_reason.reason]
    return (
        f"I didn't shortlist {excluded_reason.listing_id} because: "
        + "; ".join(reasons)
        + "."
    )


def compare_items(a: ShortlistItem, b: ShortlistItem) -> str:
    ea, eb = build_evidence(a), build_evidence(b)
    return (
        f"{ea.society_name} scores {ea.rank.score} vs {eb.society_name} at {eb.rank.score}. "
        f"{ea.society_name} matched {', '.join(ea.rank.matched) or 'none'}; "
        f"{eb.society_name} matched {', '.join(eb.rank.matched) or 'none'}. "
        "I am only comparing listing fields and rank reasons already on the shortlist."
    )


def explain_with_optional_gemini(
    item: ShortlistItem,
    *,
    question: str = "why",
    client: GeminiClient | None = None,
) -> str:
    bundle = build_evidence(item)
    base = explain_from_evidence(bundle, question=question)
    gemini = client or GeminiClient()
    if not gemini.available:
        return base
    try:
        system = (
            "Rewrite the evidence into a concise spoken assistant reply. "
            "Do NOT add any facts not present in the evidence JSON. "
            "If neighborhood evidence is missing, say exactly: "
            f"{UNVERIFIABLE}"
        )
        prompt = f"question={question}\nevidence={bundle.model_dump_json()}\ndraft={base}"
        text = gemini.generate_text(prompt, system=system)
        return text or base
    except Exception:
        return base

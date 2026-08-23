"""Deterministic listing ranking — hard filters exclude; soft prefs adjust score."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.constraints import Constraints, HardConstraints
from app.schemas.listing import Listing
from app.schemas.ranking import RankResult


class Enrichment(BaseModel):
    """Optional geospatial/lifestyle enrichment (Phase 3 fills this; stubs OK in Phase 2)."""

    listing_id: str
    near_metro: bool | None = None
    transit_poi_count: int = 0
    notes: list[str] = Field(default_factory=list)


def _norm(value: str) -> str:
    return value.strip().lower()


def _locality_matches(listing_locality: str, wanted: str) -> bool:
    left = _norm(listing_locality)
    right = _norm(wanted)
    return left == right or right in left or left in right


def _amenity_set(listing: Listing) -> set[str]:
    return {_norm(a) for a in listing.amenities}


def _hard_exclusion_reasons(listing: Listing, hard: HardConstraints) -> list[str]:
    reasons: list[str] = []
    if listing.availability_status.lower() not in {"available", "avlb", "avail"}:
        reasons.append("unavailable")
    if hard.bedrooms is not None and listing.bedrooms != hard.bedrooms:
        reasons.append("bedroom mismatch")
    if hard.locality and not _locality_matches(listing.locality, hard.locality):
        reasons.append("location mismatch")
    if hard.max_rent is not None and listing.rent > hard.max_rent:
        reasons.append("over budget")
    must = [_norm(a) for a in hard.must_have_amenities if a.strip()]
    amenities = _amenity_set(listing)
    for req in must:
        if req not in amenities:
            reasons.append(f"missing must-have: {req}")
    return reasons


def _score_components(
    listing: Listing,
    constraints: Constraints,
    enrichment: Enrichment | None,
) -> tuple[float, list[str], list[str]]:
    """Return (score 0-100, matched labels, missing soft labels)."""
    matched: list[str] = []
    missing: list[str] = []
    hard = constraints.hard
    soft = constraints.soft
    amenities = _amenity_set(listing)

    # Dimension weights (sum = 100)
    weights = {
        "budget": 20.0,
        "bedrooms": 15.0,
        "location": 15.0,
        "must_have": 20.0,
        "transit": 10.0,
        "lifestyle": 15.0,
        "availability": 5.0,
    }
    score = 0.0

    # Budget
    if hard.max_rent is not None:
        if listing.rent <= hard.max_rent:
            # Closer to budget ceiling still fine; reward being under budget
            ratio = listing.rent / hard.max_rent if hard.max_rent else 1.0
            score += weights["budget"] * (1.0 - 0.35 * ratio)
            matched.append("within budget")
        else:
            score += 0.0
    else:
        score += weights["budget"] * 0.5

    # Bedrooms
    if hard.bedrooms is not None:
        if listing.bedrooms == hard.bedrooms:
            score += weights["bedrooms"]
            matched.append(f"{listing.bedrooms}BHK")
    else:
        score += weights["bedrooms"] * 0.5

    # Location
    if hard.locality:
        if _locality_matches(listing.locality, hard.locality):
            score += weights["location"]
            matched.append("location match")
    else:
        score += weights["location"] * 0.5

    # Must-have amenities
    must = [_norm(a) for a in hard.must_have_amenities if a.strip()]
    if must:
        hits = sum(1 for req in must if req in amenities)
        score += weights["must_have"] * (hits / len(must))
        for req in must:
            if req in amenities:
                matched.append(req)
            else:
                missing.append(req)
    else:
        score += weights["must_have"] * 0.5

    # Transit (soft / enrichment)
    if soft.near_metro is True:
        if enrichment and enrichment.near_metro is True:
            score += weights["transit"]
            matched.append("near transit")
        elif enrichment and enrichment.transit_poi_count > 0:
            score += weights["transit"] * min(1.0, enrichment.transit_poi_count / 3)
            matched.append("near transit")
        else:
            # No OSM data → neutral, do not invent
            score += weights["transit"] * 0.4
            missing.append("near metro (unverified)")
    else:
        score += weights["transit"] * 0.5

    # Lifestyle soft prefs
    lifestyle_checks: list[tuple[bool | None, str]] = [
        (soft.balcony, "balcony"),
        (soft.pet_friendly, "pet-friendly"),
    ]
    wanted = [(flag, label) for flag, label in lifestyle_checks if flag is True]
    if wanted:
        hits = 0
        for flag, label in wanted:
            if label in amenities:
                hits += 1
                matched.append(label)
            else:
                missing.append(label)
        score += weights["lifestyle"] * (hits / len(wanted))
    else:
        score += weights["lifestyle"] * 0.5

    # Availability
    if listing.availability_status.lower() in {"available", "avlb", "avail"}:
        score += weights["availability"]
        matched.append("available")
    else:
        missing.append("available")

    return round(min(100.0, max(0.0, score)), 2), matched, missing


def rank_listings(
    listings: list[Listing],
    constraints: Constraints,
    enrichment: dict[str, Enrichment] | None = None,
) -> list[RankResult]:
    """Hard-fail → excluded with reasons; soft dims adjust score. Stable sort by score desc."""
    enrichment = enrichment or {}
    results: list[RankResult] = []

    for listing in listings:
        hard_reasons = _hard_exclusion_reasons(listing, constraints.hard)
        enrich = enrichment.get(listing.listing_id)
        if hard_reasons:
            results.append(
                RankResult(
                    listing_id=listing.listing_id,
                    score=0.0,
                    matched=[],
                    missing=[],
                    excluded=True,
                    exclusion_reasons=hard_reasons,
                    reason="; ".join(hard_reasons),
                )
            )
            continue

        score, matched, missing = _score_components(listing, constraints, enrich)
        if missing:
            reason = (
                f"Strong match for mandatory requirements; soft gaps: {', '.join(missing)}."
            )
        else:
            reason = "Strong match for all mandatory requirements."
        results.append(
            RankResult(
                listing_id=listing.listing_id,
                score=score,
                matched=matched,
                missing=missing,
                excluded=False,
                exclusion_reasons=[],
                reason=reason,
            )
        )

    # Stable sort: score desc, then listing_id asc for ties
    results.sort(key=lambda r: (-r.score, r.listing_id))
    return results

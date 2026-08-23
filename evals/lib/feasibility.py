"""Feasibility checks — budget, must-haves, commute/transit consistency."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.constraints import Constraints
from app.schemas.session import ShortlistItem

# Documented in evals/README.md
METRO_POI_NEAR_METRO_TOLERANCE_M = 800
UNSUPPORTED_COMMUTE_MINUTES = re.compile(r"\b\d+\s*(?:min|mins|minutes)\b", re.IGNORECASE)


@dataclass
class FeasibilityViolation:
    listing_id: str
    code: str
    message: str


def _norm(value: str) -> str:
    return value.strip().lower()


def check_budget_compliance(
    shortlist: list[ShortlistItem],
    max_rent: int | None,
) -> list[FeasibilityViolation]:
    if max_rent is None:
        return []
    violations: list[FeasibilityViolation] = []
    for item in shortlist:
        rent = item.listing.rent
        if rent > max_rent:
            violations.append(
                FeasibilityViolation(
                    listing_id=item.listing.listing_id,
                    code="budget_exceeded",
                    message=f"rent ₹{rent} exceeds max budget ₹{max_rent}",
                )
            )
    return violations


def check_must_have_compliance(
    shortlist: list[ShortlistItem],
    constraints: Constraints,
) -> list[FeasibilityViolation]:
    must = [_norm(a) for a in constraints.hard.must_have_amenities if a.strip()]
    if not must:
        return []

    violations: list[FeasibilityViolation] = []
    for item in shortlist:
        amenities = {_norm(a) for a in item.listing.amenities}
        for req in must:
            if req not in amenities:
                violations.append(
                    FeasibilityViolation(
                        listing_id=item.listing.listing_id,
                        code="must_have_missing",
                        message=f"missing must-have '{req}'",
                    )
                )
        if constraints.hard.bedrooms is not None and item.listing.bedrooms != constraints.hard.bedrooms:
            violations.append(
                FeasibilityViolation(
                    listing_id=item.listing.listing_id,
                    code="bedrooms_mismatch",
                    message=(
                        f"expected {constraints.hard.bedrooms}BHK, "
                        f"got {item.listing.bedrooms}BHK"
                    ),
                )
            )
        if constraints.hard.locality:
            wanted = _norm(constraints.hard.locality)
            locality = _norm(item.listing.locality)
            if wanted not in locality and locality not in wanted:
                violations.append(
                    FeasibilityViolation(
                        listing_id=item.listing.listing_id,
                        code="locality_mismatch",
                        message=f"locality '{item.listing.locality}' outside '{constraints.hard.locality}'",
                    )
                )
    return violations


def _nearest_metro_distance_m(item: ShortlistItem) -> float | None:
    if not item.osm or not item.osm.pois:
        return None
    metro_distances = [
        poi.distance_m
        for poi in item.osm.pois
        if poi.category == "metro" and poi.distance_m is not None
    ]
    if not metro_distances:
        return None
    return min(metro_distances)


def check_commute_consistency(
    shortlist: list[ShortlistItem],
    constraints: Constraints,
) -> list[FeasibilityViolation]:
    """
    Compare transit claims against OSM POI distances for the listing pin.

    Full route-based commute to `commute_point` is not implemented in the product;
    this check enforces internal consistency of near-metro / minute claims.
    """
    violations: list[FeasibilityViolation] = []
    for item in shortlist:
        nearest_metro_m = _nearest_metro_distance_m(item)

        if "near transit" in item.rank.matched or "near metro" in item.rank.matched:
            if nearest_metro_m is None:
                violations.append(
                    FeasibilityViolation(
                        listing_id=item.listing.listing_id,
                        code="transit_claim_unsupported",
                        message="matched near transit but no metro POI in OSM context",
                    )
                )
            elif nearest_metro_m > METRO_POI_NEAR_METRO_TOLERANCE_M:
                violations.append(
                    FeasibilityViolation(
                        listing_id=item.listing.listing_id,
                        code="transit_distance_exceeds_tolerance",
                        message=(
                            f"nearest metro POI {nearest_metro_m:.0f}m exceeds "
                            f"tolerance {METRO_POI_NEAR_METRO_TOLERANCE_M}m"
                        ),
                    )
                )

        texts = [item.rank.reason, *(n.text for n in item.neighborhood_notes or [])]
        for text in texts:
            if UNSUPPORTED_COMMUTE_MINUTES.search(text or ""):
                has_osm = nearest_metro_m is not None
                if not has_osm:
                    violations.append(
                        FeasibilityViolation(
                            listing_id=item.listing.listing_id,
                            code="unsupported_commute_minutes",
                            message="minute-level commute claim without OSM metro distance",
                        )
                    )

        if constraints.commute_point and constraints.soft.near_metro:
            if nearest_metro_m is not None and nearest_metro_m > METRO_POI_NEAR_METRO_TOLERANCE_M:
                violations.append(
                    FeasibilityViolation(
                        listing_id=item.listing.listing_id,
                        code="commute_point_transit_mismatch",
                        message=(
                            f"commute_point={constraints.commute_point!r} with near_metro pref "
                            f"but nearest metro is {nearest_metro_m:.0f}m away"
                        ),
                    )
                )

    return violations


def run_feasibility_checks(
    shortlist: list[ShortlistItem],
    constraints: Constraints,
) -> list[FeasibilityViolation]:
    return [
        *check_budget_compliance(shortlist, constraints.hard.max_rent),
        *check_must_have_compliance(shortlist, constraints),
        *check_commute_consistency(shortlist, constraints),
    ]

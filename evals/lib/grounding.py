"""Grounding & hallucination checks against authoritative data."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.listing import Listing
from app.schemas.session import ShortlistItem
from app.services.rag import UNVERIFIABLE

from evals.lib.dataset import (
    authoritative_listing_ids,
    is_listing_available,
    load_authoritative_listings_from_db,
    rag_citation_ids,
    rag_citation_urls,
)

VERIFIED_NEIGHBORHOOD_CITATION_IDS = {
    "osm",
    "listing",
    "listing-guidance",
    "listing+osm",
    "unverified",
}


@dataclass
class GroundingViolation:
    listing_id: str | None
    code: str
    message: str


def check_listing_ids_grounded(
    shortlist: list[ShortlistItem],
    authoritative_ids: set[str] | None = None,
    *,
    db=None,
) -> list[GroundingViolation]:
    if authoritative_ids is None:
        authoritative_ids = authoritative_listing_ids(db)
    violations: list[GroundingViolation] = []
    for item in shortlist:
        listing_id = item.listing.listing_id
        if listing_id not in authoritative_ids:
            violations.append(
                GroundingViolation(
                    listing_id=listing_id,
                    code="unknown_listing_id",
                    message=f"listing_id {listing_id!r} not in authoritative dataset",
                )
            )
    return violations


def check_availability_grounded(
    shortlist: list[ShortlistItem],
    authoritative: dict[str, Listing] | None = None,
    *,
    db=None,
) -> list[GroundingViolation]:
    if authoritative is None and db is not None:
        authoritative = load_authoritative_listings_from_db(db)
    violations: list[GroundingViolation] = []
    for item in shortlist:
        listing_id = item.listing.listing_id
        if item.listing.availability_status.lower() not in {"available", "avlb", "avail"}:
            violations.append(
                GroundingViolation(
                    listing_id=listing_id,
                    code="claimed_available_when_not",
                    message=f"shortlist claims availability_status={item.listing.availability_status!r}",
                )
            )
            continue
        if authoritative is None:
            continue
        if listing_id not in authoritative:
            continue
        if not is_listing_available(listing_id, authoritative):
            violations.append(
                GroundingViolation(
                    listing_id=listing_id,
                    code="dataset_unavailable",
                    message="listing marked available in shortlist but unavailable in dataset",
                )
            )
    return violations


def check_neighborhood_citations(
    shortlist: list[ShortlistItem],
    valid_rag_ids: set[str] | None = None,
    valid_rag_urls: set[str] | None = None,
) -> list[GroundingViolation]:
    valid_rag_ids = valid_rag_ids or rag_citation_ids()
    valid_rag_urls = valid_rag_urls or rag_citation_urls()
    violations: list[GroundingViolation] = []

    for item in shortlist:
        listing_id = item.listing.listing_id
        for note in item.neighborhood_notes or []:
            cid = note.citation_id
            if cid in VERIFIED_NEIGHBORHOOD_CITATION_IDS:
                continue
            if cid in valid_rag_ids:
                continue
            violations.append(
                GroundingViolation(
                    listing_id=listing_id,
                    code="missing_neighborhood_citation",
                    message=f"neighborhood note topic={note.topic!r} has invalid citation_id={cid!r}",
                )
            )

        for cite in item.citations or []:
            if cite.url and cite.url not in valid_rag_urls:
                url_lower = cite.url.lower()
                if "openstreetmap.org" in url_lower or "bengaluru.rent" in url_lower:
                    continue
                if cite.url == str(item.listing.source_url):
                    continue
                guidance_urls = {s.url for s in item.listing.neighborhood_guidance.sources}
                if cite.url not in guidance_urls:
                    violations.append(
                        GroundingViolation(
                            listing_id=listing_id,
                            code="missing_source_url",
                            message=f"citation url {cite.url!r} not in RAG or listing guidance",
                        )
                    )
    return violations


def check_missing_neighborhood_uncertainty(
    shortlist: list[ShortlistItem],
    unverified_localities: list[str] | None = None,
) -> list[GroundingViolation]:
    unverified = {_norm_locality(x) for x in (unverified_localities or [])}
    violations: list[GroundingViolation] = []

    for item in shortlist:
        locality = _norm_locality(item.listing.locality)
        if locality not in unverified:
            continue
        notes = item.neighborhood_notes or []
        if not notes:
            violations.append(
                GroundingViolation(
                    listing_id=item.listing.listing_id,
                    code="missing_uncertainty_note",
                    message=f"locality {item.listing.locality!r} unverified in RAG but no neighborhood notes",
                )
            )
            continue
        if not any(UNVERIFIABLE.lower() in (n.text or "").lower() for n in notes):
            violations.append(
                GroundingViolation(
                    listing_id=item.listing.listing_id,
                    code="missing_uncertainty_language",
                    message="RAG miss must surface explicit uncertainty text",
                )
            )
    return violations


def _norm_locality(value: str) -> str:
    return value.strip().lower()


def run_grounding_checks(
    shortlist: list[ShortlistItem],
    *,
    unverified_localities: list[str] | None = None,
    db=None,
) -> list[GroundingViolation]:
    return [
        *check_listing_ids_grounded(shortlist, db=db),
        *check_availability_grounded(shortlist, db=db),
        *check_neighborhood_citations(shortlist),
        *check_missing_neighborhood_uncertainty(shortlist, unverified_localities),
    ]

"""Shortlist builder with include/exclude reason persistence."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.constraints import Constraints
from app.schemas.listing import Listing
from app.schemas.ranking import RankResult
from app.schemas.session import ShortlistItem
from app.services.ranking import Enrichment, rank_listings

DEFAULT_MIN = 3
DEFAULT_MAX = 5


class ShortlistState(BaseModel):
    """Persisted shortlist outcome for a session search/refine."""

    constraints: Constraints
    included: list[ShortlistItem] = Field(default_factory=list)
    excluded: list[RankResult] = Field(default_factory=list)
    all_results: list[RankResult] = Field(default_factory=list)


def _is_available(listing: Listing) -> bool:
    return listing.availability_status.lower() in {"available", "avlb", "avail"}


def build_shortlist(
    listings: list[Listing],
    constraints: Constraints,
    *,
    enrichment: dict[str, Enrichment] | None = None,
    min_size: int = DEFAULT_MIN,
    max_size: int = DEFAULT_MAX,
) -> ShortlistState:
    """Rank listings and keep top 3–5 non-excluded, available results."""
    # Drop unavailable before ranking display candidates (still rank for exclude reasons)
    active = [listing for listing in listings if _is_available(listing)]
    inactive = [listing for listing in listings if not _is_available(listing)]

    ranked = rank_listings(active, constraints, enrichment)
    # Also record unavailable as excluded
    for listing in inactive:
        ranked.append(
            RankResult(
                listing_id=listing.listing_id,
                score=0.0,
                matched=[],
                missing=[],
                excluded=True,
                exclusion_reasons=["unavailable"],
                reason="unavailable",
            )
        )

    by_id = {listing.listing_id: listing for listing in listings}
    included_ranks = [r for r in ranked if not r.excluded]
    excluded_ranks = [r for r in ranked if r.excluded]

    chosen = included_ranks[:max_size]

    items: list[ShortlistItem] = []
    for rank in chosen:
        listing = by_id.get(rank.listing_id)
        if listing is None or not _is_available(listing):
            continue
        items.append(ShortlistItem(listing=listing, rank=rank, citations=[]))

    return ShortlistState(
        constraints=constraints,
        included=items,
        excluded=excluded_ranks,
        all_results=ranked,
    )


class ShortlistService:
    """Holds the latest shortlist state for a session (in-memory for Phase 2)."""

    def __init__(self) -> None:
        self.state: ShortlistState | None = None

    def rebuild(
        self,
        listings: list[Listing],
        constraints: Constraints,
        enrichment: dict[str, Enrichment] | None = None,
    ) -> ShortlistState:
        self.state = build_shortlist(listings, constraints, enrichment=enrichment)
        return self.state

    def drop_unavailable(self, available_ids: set[str]) -> ShortlistState | None:
        """Remove listings that are no longer available from the active shortlist."""
        if self.state is None:
            return None
        kept: list[ShortlistItem] = []
        newly_excluded: list[RankResult] = list(self.state.excluded)
        for item in self.state.included:
            if item.listing.listing_id in available_ids and _is_available(item.listing):
                kept.append(item)
            else:
                newly_excluded.append(
                    RankResult(
                        listing_id=item.listing.listing_id,
                        score=0.0,
                        matched=[],
                        missing=[],
                        excluded=True,
                        exclusion_reasons=["unavailable"],
                        reason="Listing became unavailable",
                    )
                )
        self.state = ShortlistState(
            constraints=self.state.constraints,
            included=kept,
            excluded=newly_excluded,
            all_results=self.state.all_results,
        )
        return self.state

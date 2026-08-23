"""Shortlist search API (Phase 2+3 — constraints → enriched scored cards)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.constraints import Constraints
from app.schemas.ranking import Citation, RankResult
from app.schemas.session import ShortlistItem
from app.services.enrichment import EnrichmentService
from app.services.retrieval import find_candidates

router = APIRouter(prefix="/shortlist", tags=["shortlist"])


class ShortlistSearchRequest(BaseModel):
    constraints: Constraints
    limit: int = Field(default=5, ge=1, le=5)
    enrich: bool = True
    osm_radius_m: int = Field(default=800, ge=100, le=3000)


class ShortlistSearchResponse(BaseModel):
    shortlist: list[ShortlistItem]
    excluded: list[RankResult]
    count: int
    citations: list[Citation] = Field(default_factory=list)
    rag_unverified_localities: list[str] = Field(default_factory=list)


def _get_enrichment_service() -> EnrichmentService:
    # Lazy singleton-ish: new service each request is fine; OSM/RAG caches are per-instance.
    # For demo stability with mocks, tests inject via dependency override.
    return EnrichmentService()


@router.post("/search", response_model=ShortlistSearchResponse, response_model_exclude_none=True)
def search_shortlist(
    body: ShortlistSearchRequest,
    db: Session = Depends(get_db),
    enrichment_service: EnrichmentService = Depends(_get_enrichment_service),
) -> ShortlistSearchResponse:
    """Rank available listings; optionally attach OSM POIs + cited neighborhood notes."""
    candidates = find_candidates(db, body.constraints.hard, limit=50)

    if not body.enrich:
        from app.services.shortlist import build_shortlist

        state = build_shortlist(candidates, body.constraints, max_size=body.limit)
        return ShortlistSearchResponse(
            shortlist=state.included,
            excluded=state.excluded,
            count=len(state.included),
        )

    enriched = enrichment_service.build_enriched_shortlist(
        candidates,
        body.constraints,
        max_size=body.limit,
        radius_m=body.osm_radius_m,
    )
    return ShortlistSearchResponse(
        shortlist=enriched.shortlist,
        excluded=enriched.excluded,
        count=len(enriched.shortlist),
        citations=enriched.citations,
        rag_unverified_localities=enriched.rag_unverified_localities,
    )

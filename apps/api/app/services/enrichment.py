"""Phase 3 enrichment: OSM per listing + RAG once per locality."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.constraints import Constraints
from app.schemas.listing import Listing
from app.schemas.osm import NeighborhoodNote, OsmContext
from app.schemas.ranking import Citation
from app.schemas.session import ShortlistItem
from app.services.citations import display_citations_for_listing
from app.services.listing_context import build_listing_neighborhood_notes, build_listing_reason
from app.services.osm import OsmService
from app.services.rag import UNVERIFIABLE, RagService, get_rag_service
from app.services.ranking import Enrichment
from app.services.shortlist import ShortlistState, build_shortlist


DEFAULT_TOPICS = ["safety", "amenities", "transit"]


class EnrichedShortlist(BaseModel):
    shortlist: list[ShortlistItem]
    excluded: list
    enrichment: dict[str, Enrichment] = Field(default_factory=dict)
    osm_by_listing: dict[str, OsmContext] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    rag_unverified_localities: list[str] = Field(default_factory=list)


class EnrichmentService:
    def __init__(
        self,
        *,
        osm: OsmService | None = None,
        rag: RagService | None = None,
    ) -> None:
        self.osm = osm or OsmService()
        self.rag = rag or get_rag_service()
        self._rag_locality_cache: dict[str, tuple[list[Citation], list[NeighborhoodNote], bool]] = {}

    def clear_caches(self) -> None:
        self.osm.clear_cache()
        self.rag.clear_cache()
        self._rag_locality_cache.clear()

    def _topics_for(self, constraints: Constraints) -> list[str]:
        topics = list(DEFAULT_TOPICS)
        if constraints.soft.near_metro is True and "transit" not in topics:
            topics.append("transit")
        return topics

    def _rag_for_locality(
        self,
        locality: str,
        constraints: Constraints,
    ) -> tuple[list[Citation], list[NeighborhoodNote], bool]:
        key = locality.strip().lower()
        if key in self._rag_locality_cache:
            return self._rag_locality_cache[key]

        query_bits = [
            locality,
            constraints.hard.locality or "",
            "near metro" if constraints.soft.near_metro else "",
            "balcony" if constraints.soft.balcony else "",
            "pet friendly" if constraints.soft.pet_friendly else "",
        ]
        query = " ".join(b for b in query_bits if b).strip() or locality
        result = self.rag.retrieve_topics(
            locality,
            query,
            self._topics_for(constraints),
            k_per_topic=1,
        )
        citations = [c.to_citation() for c in result.chunks]
        notes = [
            NeighborhoodNote(topic=c.topic, text=c.text, citation_id=c.id)
            for c in result.chunks
        ]
        unverifiable = result.unverifiable
        if unverifiable and not notes:
            notes = [
                NeighborhoodNote(
                    topic="character",
                    text=result.message or UNVERIFIABLE,
                    citation_id="unverified",
                )
            ]
        self._rag_locality_cache[key] = (citations, notes, unverifiable)
        return citations, notes, unverifiable

    def enrich_listings(
        self,
        listings: list[Listing],
        constraints: Constraints,
        *,
        radius_m: int = 800,
    ) -> tuple[dict[str, Enrichment], dict[str, OsmContext], dict[str, list[Citation]], dict[str, list[NeighborhoodNote]], list[str]]:
        enrichment: dict[str, Enrichment] = {}
        osm_by_listing: dict[str, OsmContext] = {}
        cites_by_locality: dict[str, list[Citation]] = {}
        notes_by_locality: dict[str, list[NeighborhoodNote]] = {}
        unverified: list[str] = []

        localities = sorted({listing.locality for listing in listings})
        for locality in localities:
            citations, notes, bad = self._rag_for_locality(locality, constraints)
            cites_by_locality[locality] = citations
            notes_by_locality[locality] = notes
            if bad:
                unverified.append(locality)

        for listing in listings:
            ctx = self.osm.nearby_for_listing(listing, radius_m=radius_m)
            osm_by_listing[listing.listing_id] = ctx
            enrichment[listing.listing_id] = self.osm.enrichment_from_context(ctx)

        return enrichment, osm_by_listing, cites_by_locality, notes_by_locality, unverified

    def build_enriched_shortlist(
        self,
        listings: list[Listing],
        constraints: Constraints,
        *,
        max_size: int = 5,
        radius_m: int = 800,
    ) -> EnrichedShortlist:
        enrichment, osm_map, cites_by_loc, notes_by_loc, unverified = self.enrich_listings(
            listings, constraints, radius_m=radius_m
        )
        state: ShortlistState = build_shortlist(
            listings,
            constraints,
            enrichment=enrichment,
            max_size=max_size,
        )

        all_citations: dict[str, Citation] = {}
        enriched_items: list[ShortlistItem] = []
        for item in state.included:
            loc = item.listing.locality
            citations = list(cites_by_loc.get(loc, []))
            locality_notes = list(notes_by_loc.get(loc, []))
            listing_id = item.listing.listing_id
            osm_ctx = osm_map.get(listing_id)
            formal = display_citations_for_listing(citations, item.listing, osm_ctx)
            for c in formal:
                all_citations[c.id] = c
            enrich = enrichment.get(listing_id)
            per_listing_notes = build_listing_neighborhood_notes(
                item.listing,
                osm_ctx,
                locality_notes,
                enrich,
            )
            rank_with_reason = item.rank.model_copy(
                update={"reason": build_listing_reason(item.listing, item.rank, enrich)},
            )
            enriched_items.append(
                ShortlistItem(
                    listing=item.listing,
                    rank=rank_with_reason,
                    citations=formal,
                    osm=osm_ctx,
                    neighborhood_notes=per_listing_notes,
                )
            )

        return EnrichedShortlist(
            shortlist=enriched_items,
            excluded=state.excluded,
            enrichment=enrichment,
            osm_by_listing={
                i.listing.listing_id: osm_map[i.listing.listing_id]
                for i in enriched_items
                if i.listing.listing_id in osm_map
            },
            citations=_dedupe_citations_by_url(list(all_citations.values())),
            rag_unverified_localities=unverified,
        )


def _dedupe_citations_by_url(citations: list[Citation]) -> list[Citation]:
    seen: dict[str, Citation] = {}
    for cite in citations:
        if not cite.url or cite.url in seen:
            continue
        seen[cite.url] = cite
    return list(seen.values())

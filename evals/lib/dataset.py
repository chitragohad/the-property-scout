"""Authoritative dataset loaders for evaluations."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import ListingRow
from app.schemas.listing import Listing
from app.services.rag import load_chunks
from app.services.retrieval import row_to_listing

REPO_ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_JSON = REPO_ROOT / "data" / "listings.normalized.json"
RAG_CHUNKS_JSON = REPO_ROOT / "data" / "rag" / "chunks.json"

AVAILABLE_STATUSES = {"available", "avlb", "avail"}


@lru_cache
def load_authoritative_listing_ids_from_json() -> set[str]:
    if not NORMALIZED_JSON.exists():
        raise FileNotFoundError(f"Missing authoritative dataset: {NORMALIZED_JSON}")
    payload = json.loads(NORMALIZED_JSON.read_text(encoding="utf-8"))
    listings = payload.get("listings") or []
    return {str(row["listing_id"]) for row in listings if row.get("listing_id")}


def load_authoritative_listings_from_db(db: Session) -> dict[str, Listing]:
    rows = db.query(ListingRow).all()
    return {row.listing_id: row_to_listing(row) for row in rows}


def authoritative_listing_ids(db: Session | None = None) -> set[str]:
    if db is not None:
        return set(load_authoritative_listings_from_db(db))
    return load_authoritative_listing_ids_from_json()


@lru_cache
def rag_citation_urls() -> set[str]:
    return {chunk["url"] for chunk in load_chunks(RAG_CHUNKS_JSON) if chunk.get("url")}


@lru_cache
def rag_citation_ids() -> set[str]:
    return {chunk["id"] for chunk in load_chunks(RAG_CHUNKS_JSON) if chunk.get("id")}


def is_listing_available(listing_id: str, listings: dict[str, Listing]) -> bool:
    listing = listings.get(listing_id)
    if listing is None:
        return False
    return listing.availability_status.lower() in AVAILABLE_STATUSES


def listing_guidance_citation_urls(listing: Listing) -> set[str]:
    return {source.url for source in listing.neighborhood_guidance.sources if source.url}

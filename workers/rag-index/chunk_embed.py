"""Build locality×topic RAG chunks (section-aware + seed bootstrap)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = ROOT / "data" / "rag" / "chunks.json"
NORMALIZED = ROOT / "data" / "listings.normalized.json"

TOPICS = frozenset({"safety", "amenities", "transit", "lifestyle", "character"})
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "safety": ("safe", "safety", "security", "crime", "police", "well-lit", "lighting"),
    "amenities": (
        "amenity",
        "amenities",
        "market",
        "shop",
        "grocery",
        "cafe",
        "restaurant",
        "school",
        "hospital",
        "park",
        "mall",
    ),
    "transit": (
        "transit",
        "metro",
        "bus",
        "road",
        "traffic",
        "commute",
        "station",
        "connectivity",
        "namma",
    ),
    "lifestyle": ("lifestyle", "nightlife", "residential", "family", "culture", "crowd"),
    "character": ("neighbourhood", "neighborhood", "locality", "layout", "area", "suburb"),
}


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_id_for(locality: str, topic: str, url: str, text: str) -> str:
    digest = hashlib.sha256(
        f"{locality.lower()}|{topic}|{url}|{_norm_ws(text).lower()}".encode()
    ).hexdigest()[:16]
    loc_slug = re.sub(r"[^a-z0-9]+", "-", locality.lower()).strip("-")
    return f"{loc_slug}:{topic}:{digest}"


def dedup_key(locality: str, topic: str, url: str, text: str) -> str:
    return hashlib.sha256(
        f"{locality.lower()}|{topic}|{url}|{_norm_ws(text).lower()}".encode()
    ).hexdigest()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _section_chunks(text: str, *, max_chars: int = 1200, min_chars: int = 280) -> list[str]:
    """Split long source text into ~200–400 token-ish character windows on sentence boundaries."""
    text = _norm_ws(text)
    if not text:
        return []
    # Sentence-ish split
    parts = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        candidate = f"{buf} {part}".strip() if buf else part
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if len(buf) >= min_chars:
            chunks.append(buf)
            buf = part
        else:
            # Hard cut oversized sentence
            while len(candidate) > max_chars:
                chunks.append(candidate[:max_chars].rsplit(" ", 1)[0])
                candidate = candidate[max_chars:].lstrip()
            buf = candidate
    if buf and len(buf) >= min(min_chars, 120):
        chunks.append(buf)
    return chunks[:40]  # cap per source


def _guess_topic(text: str) -> str:
    tokens = set(_tokenize(text))
    best = "character"
    best_score = -1
    for topic, keys in TOPIC_KEYWORDS.items():
        score = sum(1 for k in keys if k in tokens or any(k in t for t in tokens))
        if score > best_score:
            best_score = score
            best = topic
    return best


def chunks_from_source(
    *,
    locality: str,
    title: str,
    url: str,
    text: str,
    origin: str = "source",
) -> list[dict[str, Any]]:
    if not title.strip() or not url.strip():
        return []
    out: list[dict[str, Any]] = []
    for i, piece in enumerate(_section_chunks(text)):
        topic = _guess_topic(piece)
        if topic not in TOPICS:
            topic = "character"
        snippet = piece[:240]
        out.append(
            {
                "id": chunk_id_for(locality, topic, url, piece),
                "text": piece,
                "title": title,
                "url": url,
                "snippet": snippet,
                "locality": locality,
                "topic": topic,
                "section_heading": f"section-{i + 1}",
                "origin": origin,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return out


def seed_chunks_from_normalized(path: Path | None = None) -> list[dict[str, Any]]:
    """Bootstrap locality×topic chunks from deduped neighborhood_guidance."""
    target = path or NORMALIZED
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    listings = data.get("listings") or []
    seen: set[str] = set()
    chunks: list[dict[str, Any]] = []
    for listing in listings:
        guidance = listing.get("neighborhood_guidance") or {}
        locality = str(guidance.get("locality") or listing.get("locality") or "").strip()
        if not locality:
            continue
        sources = guidance.get("sources") or []
        source = sources[0] if sources else {}
        title = str(source.get("title") or f"{locality} neighborhood notes")
        url = str(source.get("url") or "").strip()
        if not url:
            continue  # citation contract: no url → cannot index
        topic_map = {
            "safety": guidance.get("safety"),
            "amenities": guidance.get("amenities"),
            "transit": guidance.get("transit_character"),
        }
        for topic, text in topic_map.items():
            if not text or not str(text).strip():
                continue
            body = _norm_ws(str(text))
            key = dedup_key(locality, topic, url, body)
            if key in seen:
                continue
            seen.add(key)
            chunks.append(
                {
                    "id": chunk_id_for(locality, topic, url, body),
                    "text": body,
                    "title": title,
                    "url": url,
                    "snippet": body[:240],
                    "locality": locality,
                    "topic": topic,
                    "section_heading": topic,
                    "origin": "seed",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    return chunks


def _merge_prefer_source(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedup by locality+topic+url+text; prefer origin=source over seed."""
    best: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        if not chunk.get("title") or not chunk.get("url"):
            continue
        key = dedup_key(chunk["locality"], chunk["topic"], chunk["url"], chunk["text"])
        existing = best.get(key)
        if existing is None:
            best[key] = chunk
            continue
        if existing.get("origin") == "seed" and chunk.get("origin") == "source":
            best[key] = chunk
    # Also demote seed when any source exists for same locality+topic
    by_lt: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for chunk in best.values():
        by_lt.setdefault((chunk["locality"].lower(), chunk["topic"]), []).append(chunk)
    final: list[dict[str, Any]] = []
    for group in by_lt.values():
        has_source = any(c.get("origin") == "source" for c in group)
        for c in group:
            if has_source and c.get("origin") == "seed":
                continue
            final.append(c)
    final.sort(key=lambda c: (c["locality"], c["topic"], c["id"]))
    return final


def build_tf_weights(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach simple TF vectors for offline lexical retrieval (no heavy ML deps)."""
    enriched = []
    for chunk in chunks:
        counts = Counter(_tokenize(chunk["text"]))
        total = sum(counts.values()) or 1
        tf = {t: n / total for t, n in counts.items()}
        row = dict(chunk)
        row["tf"] = tf
        enriched.append(row)
    return enriched


def write_index(chunks: list[dict[str, Any]], path: Path | None = None) -> Path:
    target = path or DEFAULT_INDEX
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "strategy": "locality×topic×source",
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def build_index(
    *,
    include_seeds: bool = True,
    raw_sources: list[dict[str, Any]] | None = None,
    out_path: Path | None = None,
) -> Path:
    chunks: list[dict[str, Any]] = []
    if include_seeds:
        chunks.extend(seed_chunks_from_normalized())
    for src in raw_sources or []:
        if not src.get("ok") or not src.get("text"):
            continue
        chunks.extend(
            chunks_from_source(
                locality=src["locality"],
                title=src["title"],
                url=src["url"],
                text=src["text"],
                origin="source",
            )
        )
    merged = _merge_prefer_source(chunks)
    weighted = build_tf_weights(merged)
    return write_index(weighted, out_path)


def main() -> None:
    from fetch_sources import load_raw

    raw = load_raw()
    path = build_index(include_seeds=True, raw_sources=raw)
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"Wrote RAG index → {path} chunks={data['chunk_count']}")


if __name__ == "__main__":
    main()

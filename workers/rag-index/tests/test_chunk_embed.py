"""Tests for locality×topic chunking / seed bootstrap."""

from __future__ import annotations

import json
from pathlib import Path

from chunk_embed import build_index, seed_chunks_from_normalized


def test_seed_chunks_dedupe_by_locality_topic():
    chunks = seed_chunks_from_normalized()
    assert chunks
    keys = {(c["locality"], c["topic"], c["url"]) for c in chunks}
    # Far fewer than listing count when localities repeat
    assert len(chunks) == len({c["id"] for c in chunks})
    assert all(c["url"] and c["title"] for c in chunks)
    assert all(c["origin"] == "seed" for c in chunks)
    # Koramangala should appear once per topic, not once per listing
    km_safety = [c for c in chunks if c["locality"] == "Koramangala" and c["topic"] == "safety"]
    assert len(km_safety) == 1


def test_build_index_writes_file(tmp_path: Path):
    path = build_index(include_seeds=True, raw_sources=[], out_path=tmp_path / "chunks.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["chunk_count"] > 0
    assert data["strategy"] == "locality×topic×source"
    topics = {c["topic"] for c in data["chunks"]}
    assert "safety" in topics
    assert "amenities" in topics
    assert "transit" in topics

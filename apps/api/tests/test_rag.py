"""Tests for neighborhood RAG retrieve + citation contract."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.rag import UNVERIFIABLE, RagService


def _write_index(tmp_path: Path, chunks: list[dict]) -> Path:
    path = tmp_path / "chunks.json"
    path.write_text(
        json.dumps({"version": 1, "chunk_count": len(chunks), "chunks": chunks}),
        encoding="utf-8",
    )
    return path


def test_empty_index_returns_unverifiable(tmp_path: Path):
    path = _write_index(tmp_path, [])
    svc = RagService(index_path=path)
    result = svc.retrieve("Koramangala", "is it safe?", topic="safety", k=2)
    assert result.unverifiable is True
    assert result.message == UNVERIFIABLE
    assert result.chunks == []


def test_rejects_chunks_missing_url_or_title(tmp_path: Path):
    path = _write_index(
        tmp_path,
        [
            {
                "id": "bad-1",
                "text": "Safety notes",
                "title": "",
                "url": "https://example.com",
                "snippet": "Safety notes",
                "locality": "Koramangala",
                "topic": "safety",
                "tf": {"safety": 1.0},
            },
            {
                "id": "bad-2",
                "text": "Transit notes",
                "title": "Title",
                "url": "",
                "snippet": "Transit notes",
                "locality": "Koramangala",
                "topic": "transit",
                "tf": {"transit": 1.0},
            },
        ],
    )
    svc = RagService(index_path=path)
    result = svc.retrieve("Koramangala", "safety", topic="safety")
    assert result.unverifiable is True


def test_metadata_filter_then_rank(tmp_path: Path):
    path = _write_index(
        tmp_path,
        [
            {
                "id": "km-safety",
                "text": "Koramangala is generally regarded as a busy well-lit area with steady evening footfall.",
                "title": "Koramangala — Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Koramangala",
                "snippet": "busy well-lit area",
                "locality": "Koramangala",
                "topic": "safety",
                "origin": "seed",
                "tf": {"koramangala": 0.2, "busy": 0.2, "well": 0.1, "lit": 0.1, "area": 0.2, "evening": 0.2},
            },
            {
                "id": "hsr-safety",
                "text": "HSR Layout has organised streets and residential associations.",
                "title": "HSR Layout — Wikipedia",
                "url": "https://en.wikipedia.org/wiki/HSR_Layout",
                "snippet": "organised streets",
                "locality": "HSR Layout",
                "topic": "safety",
                "origin": "seed",
                "tf": {"hsr": 0.3, "layout": 0.3, "streets": 0.2, "residential": 0.2},
            },
            {
                "id": "km-transit",
                "text": "Koramangala has frequent bus coverage and metro catchments.",
                "title": "Koramangala — Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Koramangala",
                "snippet": "bus coverage",
                "locality": "Koramangala",
                "topic": "transit",
                "origin": "seed",
                "tf": {"koramangala": 0.2, "bus": 0.3, "metro": 0.3, "coverage": 0.2},
            },
        ],
    )
    svc = RagService(index_path=path)
    result = svc.retrieve("Koramangala", "well lit safety", topic="safety", k=2)
    assert result.unverifiable is False
    assert len(result.chunks) == 1
    assert result.chunks[0].id == "km-safety"
    cite = result.chunks[0].to_citation()
    assert cite.url.startswith("https://")
    assert cite.locality == "Koramangala"
    assert cite.topic == "safety"

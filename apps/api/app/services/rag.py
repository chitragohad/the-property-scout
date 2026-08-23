"""Neighborhood RAG retrieval — metadata filter then lexical rank."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.ranking import Citation

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INDEX = ROOT / "data" / "rag" / "chunks.json"

UNVERIFIABLE = "I couldn't find reliable public information to verify this."


class CitedChunk(BaseModel):
    id: str
    text: str
    title: str
    url: str
    snippet: str
    locality: str
    topic: str
    score: float = 0.0
    origin: str = "source"

    def to_citation(self) -> Citation:
        return Citation(
            id=self.id,
            title=self.title,
            url=self.url,
            snippet=self.snippet or self.text[:240],
            locality=self.locality,
            topic=self.topic,
        )


class RagRetrieveResult(BaseModel):
    chunks: list[CitedChunk] = Field(default_factory=list)
    unverifiable: bool = False
    message: str | None = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values())) or 1.0
    nb = math.sqrt(sum(v * v for v in b.values())) or 1.0
    return dot / (na * nb)


def _locality_match(chunk_locality: str, wanted: str) -> bool:
    left = chunk_locality.strip().lower()
    right = wanted.strip().lower()
    return left == right or right in left or left in right


def load_chunks(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DEFAULT_INDEX
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    chunks = data.get("chunks") or []
    return [c for c in chunks if c.get("title") and c.get("url") and c.get("text")]


class RagService:
    def __init__(self, index_path: Path | None = None) -> None:
        self.index_path = index_path or DEFAULT_INDEX
        self._chunks: list[dict[str, Any]] | None = None
        self._cache: dict[tuple[str, str | None, str, int], RagRetrieveResult] = {}

    def clear_cache(self) -> None:
        self._cache.clear()
        self._chunks = None

    def _ensure_loaded(self) -> list[dict[str, Any]]:
        if self._chunks is None:
            self._chunks = load_chunks(self.index_path)
        return self._chunks

    def retrieve(
        self,
        locality: str,
        query: str,
        *,
        topic: str | None = None,
        k: int = 3,
    ) -> RagRetrieveResult:
        cache_key = (locality.strip().lower(), topic, query.strip().lower(), k)
        if cache_key in self._cache:
            return self._cache[cache_key]

        chunks = self._ensure_loaded()
        if not chunks:
            result = RagRetrieveResult(chunks=[], unverifiable=True, message=UNVERIFIABLE)
            self._cache[cache_key] = result
            return result

        filtered = [c for c in chunks if _locality_match(str(c["locality"]), locality)]
        if topic:
            topic_l = topic.strip().lower()
            filtered = [c for c in filtered if str(c.get("topic", "")).lower() == topic_l]

        if not filtered:
            result = RagRetrieveResult(chunks=[], unverifiable=True, message=UNVERIFIABLE)
            self._cache[cache_key] = result
            return result

        q_tokens = _tokenize(query) or _tokenize(topic or locality)
        q_tf: dict[str, float] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0.0) + 1.0
        total = sum(q_tf.values()) or 1.0
        q_tf = {t: n / total for t, n in q_tf.items()}

        scored: list[CitedChunk] = []
        for c in filtered:
            tf = c.get("tf") or {}
            if not tf:
                counts: dict[str, float] = {}
                toks = _tokenize(c["text"])
                for t in toks:
                    counts[t] = counts.get(t, 0.0) + 1.0
                n = sum(counts.values()) or 1.0
                tf = {t: v / n for t, v in counts.items()}
            score = _cosine(q_tf, {str(k): float(v) for k, v in tf.items()})
            # Prefer source over seed on ties via tiny boost
            if c.get("origin") == "source":
                score += 0.01
            scored.append(
                CitedChunk(
                    id=str(c["id"]),
                    text=str(c["text"]),
                    title=str(c["title"]),
                    url=str(c["url"]),
                    snippet=str(c.get("snippet") or c["text"][:240]),
                    locality=str(c["locality"]),
                    topic=str(c["topic"]),
                    score=round(score, 4),
                    origin=str(c.get("origin") or "source"),
                )
            )

        scored.sort(key=lambda x: (-x.score, x.id))
        top = scored[: max(1, k)]
        if not top or all(x.score <= 0 and not q_tokens for x in top):
            # Still return locality-filtered chunks when query is empty-ish
            top = scored[: max(1, k)]

        if not top:
            result = RagRetrieveResult(chunks=[], unverifiable=True, message=UNVERIFIABLE)
        else:
            result = RagRetrieveResult(chunks=top, unverifiable=False, message=None)
        self._cache[cache_key] = result
        return result

    def retrieve_topics(
        self,
        locality: str,
        query: str,
        topics: list[str],
        *,
        k_per_topic: int = 1,
    ) -> RagRetrieveResult:
        merged: list[CitedChunk] = []
        seen: set[str] = set()
        for topic in topics:
            part = self.retrieve(locality, query or topic, topic=topic, k=k_per_topic)
            for chunk in part.chunks:
                if chunk.id in seen:
                    continue
                seen.add(chunk.id)
                merged.append(chunk)
        if not merged:
            return RagRetrieveResult(chunks=[], unverifiable=True, message=UNVERIFIABLE)
        return RagRetrieveResult(chunks=merged, unverifiable=False, message=None)


@lru_cache
def get_rag_service() -> RagService:
    return RagService()

"""Session store — in-memory (local) or Redis (Vercel/serverless)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import get_settings
from app.schemas.constraints import Constraints
from app.schemas.ranking import Citation, RankResult
from app.schemas.session import (
    Booking,
    ConversationTurn,
    SessionPhase,
    SessionSnapshot,
    ShortlistItem,
)
from app.services.constraints import ConstraintManager
from app.services.enrichment import EnrichmentService

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24  # 24h


@dataclass
class SessionRecord:
    session_id: str
    phase: SessionPhase = "idle"
    constraints: ConstraintManager = field(default_factory=ConstraintManager)
    shortlist: list[ShortlistItem] = field(default_factory=list)
    excluded: list[RankResult] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    booking: Booking | None = None
    turns: list[ConversationTurn] = field(default_factory=list)
    selected_listing_id: str | None = None
    enrichment: EnrichmentService = field(default_factory=EnrichmentService)
    awaiting_explicit_confirm: bool = False

    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            session_id=self.session_id,
            phase=self.phase,
            clarification_count=self.constraints.clarification_count,
            constraints=self.constraints.constraints,
            shortlist=list(self.shortlist),
            citations=list(self.citations),
            booking=self.booking,
            turns=list(self.turns),
            selected_listing_id=self.selected_listing_id,
        )


def serialize_session(record: SessionRecord) -> dict[str, Any]:
    """JSON-safe payload for Redis (enrichment caches are rebuilt on load)."""
    return {
        "session_id": record.session_id,
        "phase": record.phase,
        "constraints": record.constraints.constraints.model_dump(mode="json"),
        "clarification_count": record.constraints.clarification_count,
        "max_clarifications": record.constraints.max_clarifications,
        "shortlist": [item.model_dump(mode="json") for item in record.shortlist],
        "excluded": [item.model_dump(mode="json") for item in record.excluded],
        "citations": [item.model_dump(mode="json") for item in record.citations],
        "booking": record.booking.model_dump(mode="json") if record.booking else None,
        "turns": [item.model_dump(mode="json") for item in record.turns],
        "selected_listing_id": record.selected_listing_id,
        "awaiting_explicit_confirm": record.awaiting_explicit_confirm,
    }


def deserialize_session(data: dict[str, Any]) -> SessionRecord:
    constraints = ConstraintManager(
        initial=Constraints.model_validate(data.get("constraints") or {}),
        max_clarifications=int(data.get("max_clarifications") or 5),
    )
    constraints.clarification_count = int(data.get("clarification_count") or 0)

    booking_raw = data.get("booking")
    return SessionRecord(
        session_id=str(data["session_id"]),
        phase=data.get("phase") or "idle",
        constraints=constraints,
        shortlist=[ShortlistItem.model_validate(item) for item in data.get("shortlist") or []],
        excluded=[RankResult.model_validate(item) for item in data.get("excluded") or []],
        citations=[Citation.model_validate(item) for item in data.get("citations") or []],
        booking=Booking.model_validate(booking_raw) if booking_raw else None,
        turns=[ConversationTurn.model_validate(item) for item in data.get("turns") or []],
        selected_listing_id=data.get("selected_listing_id"),
        enrichment=EnrichmentService(),
        awaiting_explicit_confirm=bool(data.get("awaiting_explicit_confirm")),
    )


class SessionStoreProtocol(Protocol):
    def create(self) -> SessionRecord: ...

    def get(self, session_id: str) -> SessionRecord | None: ...

    def save(self, record: SessionRecord) -> None: ...

    def require(self, session_id: str) -> SessionRecord: ...

    def clear(self) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def create(self) -> SessionRecord:
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        record = SessionRecord(session_id=session_id)
        self._sessions[session_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def save(self, record: SessionRecord) -> None:
        self._sessions[record.session_id] = record

    def require(self, session_id: str) -> SessionRecord:
        record = self.get(session_id)
        if record is None:
            raise KeyError(session_id)
        return record

    def clear(self) -> None:
        self._sessions.clear()


class RedisSessionStore:
    """Upstash / Redis-backed sessions for Vercel serverless."""

    def __init__(self, redis_url: str, *, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> None:
        import redis

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    @staticmethod
    def _key(session_id: str) -> str:
        return f"property-scout:session:{session_id}"

    def create(self) -> SessionRecord:
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        record = SessionRecord(session_id=session_id)
        self.save(record)
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        raw = self._client.get(self._key(session_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt session payload for %s", session_id)
            return None
        return deserialize_session(data)

    def save(self, record: SessionRecord) -> None:
        payload = json.dumps(serialize_session(record), separators=(",", ":"))
        self._client.set(self._key(record.session_id), payload, ex=self._ttl)

    def require(self, session_id: str) -> SessionRecord:
        record = self.get(session_id)
        if record is None:
            raise KeyError(session_id)
        return record

    def clear(self) -> None:
        keys = list(self._client.scan_iter(match=self._key("*")))
        if keys:
            self._client.delete(*keys)


# Back-compat alias used by tests and imports
SessionStore = InMemorySessionStore

_STORE: SessionStoreProtocol | None = None


def reset_session_store() -> None:
    """Test helper — rebuild store after env changes."""
    global _STORE
    _STORE = None


def get_session_store() -> SessionStoreProtocol:
    global _STORE
    if _STORE is not None:
        return _STORE

    settings = get_settings()
    redis_url = (settings.redis_url or "").strip()
    if redis_url:
        try:
            import redis

            client = redis.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            _STORE = RedisSessionStore(
                redis_url,
                ttl_seconds=settings.session_ttl_seconds,
            )
            logger.info("Using Redis session store")
            return _STORE
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis session store unavailable (%s); using in-memory", exc)
            _STORE = InMemorySessionStore()
            return _STORE

    _STORE = InMemorySessionStore()
    return _STORE

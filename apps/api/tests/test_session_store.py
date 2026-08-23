"""Session store serialize/deserialize and save persistence tests."""

from __future__ import annotations

from app.schemas.constraints import Constraints, HardConstraints
from app.services.constraints import ConstraintManager
from app.services.session_store import (
    InMemorySessionStore,
    SessionRecord,
    deserialize_session,
    serialize_session,
)
from tests.test_explain import _item


def test_serialize_roundtrip_preserves_constraints_and_phase():
    mgr = ConstraintManager(
        initial=Constraints(hard=HardConstraints(bedrooms=2, locality="Koramangala", max_rent=35000))
    )
    mgr.clarification_count = 1
    record = SessionRecord(
        session_id="sess-test123",
        phase="awaiting_confirm",
        constraints=mgr,
        awaiting_explicit_confirm=True,
    )
    restored = deserialize_session(serialize_session(record))
    assert restored.session_id == "sess-test123"
    assert restored.phase == "awaiting_confirm"
    assert restored.awaiting_explicit_confirm is True
    assert restored.constraints.clarification_count == 1
    assert restored.constraints.constraints.hard.bedrooms == 2
    assert restored.constraints.constraints.hard.locality == "Koramangala"
    assert restored.constraints.constraints.hard.max_rent == 35000


def test_serialize_roundtrip_shortlist():
    item = _item()
    record = SessionRecord(
        session_id="sess-sl",
        phase="shortlist",
        shortlist=[item],
        selected_listing_id=item.listing.listing_id,
    )
    restored = deserialize_session(serialize_session(record))
    assert len(restored.shortlist) == 1
    assert restored.shortlist[0].listing.listing_id == item.listing.listing_id
    assert restored.selected_listing_id == item.listing.listing_id
    assert restored.shortlist[0].rank.score == item.rank.score


def test_in_memory_save_persists_mutations():
    store = InMemorySessionStore()
    record = store.create()
    record.phase = "clarifying"
    store.save(record)
    loaded = store.get(record.session_id)
    assert loaded is not None
    assert loaded.phase == "clarifying"

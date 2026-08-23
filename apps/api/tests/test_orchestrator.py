"""Orchestrator pipeline tests — prefs → confirm → shortlist → why → refine."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_session_factory, init_db, reset_engine_cache
from app.services.orchestrator import OrchestratorDeps, handle_turn
from app.services.session_store import SessionStore


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Session:
    db_path = tmp_path / "orch.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OSM_MODE", "static")
    get_settings.cache_clear()
    reset_engine_cache()
    init_db()

    # Seed listings
    import sys

    ingest = Path(__file__).resolve().parents[3] / "workers" / "ingest"
    if str(ingest) not in sys.path:
        sys.path.insert(0, str(ingest))
    from upsert import run_ingest

    run_ingest(use_seed=True)
    session = get_session_factory()()
    yield session
    session.close()
    get_settings.cache_clear()
    reset_engine_cache()
    os.environ.pop("DATABASE_URL", None)


def test_scripted_conversation_prefs_confirm_why_refine(db_session: Session):
    store = SessionStore()
    record = store.create()
    deps = OrchestratorDeps(db=db_session, gemini=None)

    r1 = handle_turn(
        record,
        "I'm looking for a 2BHK in Koramangala under 35,000. I need parking and close to metro.",
        deps,
    )
    assert r1.phase == "awaiting_confirm"
    assert record.constraints.constraints.hard.bedrooms == 2
    assert record.constraints.constraints.hard.locality == "Koramangala"
    assert record.constraints.constraints.hard.max_rent == 35000
    assert "parking" in record.constraints.constraints.hard.must_have_amenities

    r2 = handle_turn(record, "yes, confirm", deps)
    assert r2.phase == "shortlist"
    assert r2.shortlist
    assert 1 <= len(r2.shortlist) <= 5
    for item in r2.shortlist:
        assert item.listing.bedrooms == 2
        assert item.listing.rent <= 35000

    r3 = handle_turn(record, "why the first one?", deps)
    assert "match" in r3.assistant_text.lower() or "BHK" in r3.assistant_text

    # Refine budget; bedrooms/locality/parking must remain
    r4 = handle_turn(record, "actually make the budget under 30000", deps)
    assert record.constraints.constraints.hard.max_rent == 30000
    assert record.constraints.constraints.hard.bedrooms == 2
    assert record.constraints.constraints.hard.locality == "Koramangala"
    assert "parking" in record.constraints.constraints.hard.must_have_amenities
    assert r4.phase == "shortlist"
    assert r4.shortlist is not None
    for item in r4.shortlist:
        assert item.listing.rent <= 30000

    # Preference edit without "change/actually" verbs still re-searches in shortlist phase
    before_ids = {i.listing.listing_id for i in record.shortlist}
    r5 = handle_turn(record, "under 28000", deps)
    assert record.constraints.constraints.hard.max_rent == 28000
    assert r5.phase == "shortlist"
    assert r5.shortlist is not None
    for item in r5.shortlist:
        assert item.listing.rent <= 28000

    # Remove a listing from the current shortlist without a full re-search wipe
    assert len(record.shortlist) >= 1
    first_name = record.shortlist[0].listing.society_name
    before_count = len(record.shortlist)
    r6 = handle_turn(record, "remove the first one", deps)
    assert "Removed" in r6.assistant_text
    assert first_name in r6.assistant_text
    assert r6.shortlist is not None
    assert len(r6.shortlist) == before_count - 1
    assert all(i.listing.society_name != first_name for i in r6.shortlist)
    # Unrelated hard constraints preserved after remove
    assert record.constraints.constraints.hard.max_rent == 28000
    assert before_ids  # sanity: we had listings before refine chain

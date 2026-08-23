"""Session HTTP API tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.session import init_db, reset_engine_cache
from app.services.session_store import get_session_store, reset_session_store

INGEST_ROOT = Path(__file__).resolve().parents[3] / "workers" / "ingest"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "session.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OSM_MODE", "static")
    monkeypatch.delenv("REDIS_URL", raising=False)
    get_settings.cache_clear()
    reset_engine_cache()
    reset_session_store()
    init_db()
    if str(INGEST_ROOT) not in sys.path:
        sys.path.insert(0, str(INGEST_ROOT))
    from upsert import run_ingest

    run_ingest(use_seed=True)
    get_session_store().clear()

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_session_store().clear()
    reset_session_store()
    get_settings.cache_clear()
    reset_engine_cache()
    os.environ.pop("DATABASE_URL", None)


def test_create_get_and_turn_flow(client: TestClient):
    created = client.post("/session")
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    assert session_id

    got = client.get(f"/session/{session_id}")
    assert got.status_code == 200
    assert got.json()["phase"] == "idle"

    turn = client.post(
        f"/session/{session_id}/turn",
        json={
            "text": (
                "I'm looking for a 2BHK in Koramangala under 35000. "
                "I need parking and close to a metro."
            )
        },
    )
    assert turn.status_code == 200
    body = turn.json()
    assert body["phase"] == "awaiting_confirm"
    assert body["constraints"]["hard"]["bedrooms"] == 2
    assert body["assistant_text"]

    confirmed = client.post(f"/session/{session_id}/confirm-search")
    assert confirmed.status_code == 200
    cbody = confirmed.json()
    assert cbody["phase"] == "shortlist"
    assert cbody["shortlist"]
    listing_id = cbody["shortlist"][0]["listing"]["listing_id"]

    selected = client.post(
        f"/session/{session_id}/select-listing",
        json={"listing_id": listing_id},
    )
    assert selected.status_code == 200
    assert selected.json()["selected_listing_id"] == listing_id

    booked = client.post(
        f"/session/{session_id}/bookings",
        json={"listing_id": listing_id, "date": "2026-08-22", "slot": "16:00"},
    )
    assert booked.status_code == 200
    body = booked.json()
    assert body["status"] == "confirmed"
    assert body["confirmation_code"]
    assert len(body["confirmation_code"]) == 6

    slots = client.get(f"/session/{session_id}/booking/slots", params={"date": "2026-08-22"})
    assert slots.status_code == 200
    assert "16:00" in slots.json()["slots"]

    exported = client.post(
        f"/session/{session_id}/export",
        json={"email": "renter@example.com"},
    )
    assert exported.status_code == 200
    assert exported.json()["ok"] is True

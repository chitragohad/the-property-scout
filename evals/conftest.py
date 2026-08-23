"""Shared fixtures for AI evaluation suites."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"

sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from app.config import get_settings  # noqa: E402
from app.db.session import get_session_factory, init_db, reset_engine_cache  # noqa: E402
from app.services.orchestrator import OrchestratorDeps, confirm_search, handle_turn  # noqa: E402
from app.services.session_store import SessionRecord, SessionStore  # noqa: E402
from evals.lib.report import clear_results, print_report  # noqa: E402


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Session:
    db_path = tmp_path / "evals.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OSM_MODE", "static")
    get_settings.cache_clear()
    reset_engine_cache()
    init_db()

    ingest = REPO_ROOT / "workers" / "ingest"
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


@pytest.fixture()
def orchestrator_deps(db_session: Session) -> OrchestratorDeps:
    return OrchestratorDeps(db=db_session, gemini=None)


@pytest.fixture()
def session_record() -> SessionRecord:
    return SessionStore().create()


def run_prefs_confirm(
    record: SessionRecord,
    deps: OrchestratorDeps,
    *,
    prefs: str = (
        "I'm looking for a 2BHK in Koramangala under 35000. I need parking and close to metro."
    ),
) -> None:
    handle_turn(record, prefs, deps)
    confirm_search(record, deps)


def pytest_sessionstart(session) -> None:  # noqa: ARG001
    clear_results()


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    print_report()

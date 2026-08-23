from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base


def default_sqlite_url() -> str:
    """Local SQLite under repo data/; on Vercel use /tmp (read-only FS elsewhere)."""
    import os

    if os.environ.get("VERCEL") == "1":
        return "sqlite:////tmp/property_scout.db"

    # apps/api/app/db/session.py → repo root is parents[4] in monorepo checkout
    candidates = [
        Path(__file__).resolve().parents[4] / "data",
        Path("/tmp"),
    ]
    for data_dir in candidates:
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{data_dir / 'property_scout.db'}"
        except OSError:
            continue
    return "sqlite:////tmp/property_scout.db"


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url or default_sqlite_url()
    # Neon / Vercel often provide postgres:// — SQLAlchemy + psycopg3 need this form.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://") :]

    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_engine_cache() -> None:
    """Test helper to rebuild engines after DATABASE_URL changes."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()

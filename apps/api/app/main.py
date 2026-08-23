import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import init_db
from app.routers import listings, session, shortlist, snapshots, voice

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 — keep /health up on Vercel misconfig
        logger.exception("Database init failed (listings may be unavailable): %s", exc)
    yield


app = FastAPI(
    title="Property Scout API",
    version="0.1.0",
    description="Voice-first AI property discovery orchestration API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router)
app.include_router(snapshots.router)
app.include_router(shortlist.router)
app.include_router(session.router)
app.include_router(voice.router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    current = get_settings()
    return {
        "status": "ok",
        "n8n_enabled": bool((current.n8n_webhook_url or "").strip()),
    }

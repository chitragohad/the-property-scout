# Property Scout

Voice-first AI property discovery assistant for Bengaluru.

## Prerequisites

- Node.js 20+
- [pnpm](https://pnpm.io/) 9+
- Python 3.11+ (3.12 recommended; `python3.12` on Homebrew)

## Setup

```bash
# JS workspaces (web + shared schemas)
pnpm install

# Python API
cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ../..

# Env
cp .env.example .env
```

> Tip: if `python3` is 3.9 on macOS, use `/opt/homebrew/bin/python3.12` explicitly.
## Run

Terminal 1 — API:

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 — Web:

```bash
pnpm dev
```

- Web: http://localhost:3000  
- API health: http://localhost:8000/health → `{"status":"ok"}`
- Listings: http://localhost:8000/listings?locality=Koramangala&bedrooms=2&max_rent=35000&must_have=parking
- Shortlist search (Phase 2): `POST /shortlist/search` with JSON constraints → 3–5 scored cards

## Ingest listings (Phase 1)

Uses scrubbed seed data modeled on [bengaluru.rent](https://bengaluru.rent/) (PII stripped; “Not for rent” excluded). Optional: set `INGEST_JSON_PATH` to a local JSON dump.

```bash
cd apps/api && source .venv/bin/activate
cd ../../workers/ingest
python upsert.py
```

## Tests

```bash
# API + retrieval
cd apps/api && source .venv/bin/activate && pytest -v

# Ingest worker
cd workers/ingest && ../../apps/api/.venv/bin/pytest -v
```

## LLM config

```env
GEMINI_API_KEY=your_key
LLM_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
```

Used from Phase 4 onward for intent, preference extraction, and grounded explanations.

## Deploy (Vercel — frontend + API)

Full plan: [`docs/superpowers/plans/2026-08-23-vercel-deployment.md`](docs/superpowers/plans/2026-08-23-vercel-deployment.md)

**Two Vercel projects** from the same repo:

| Project | Root Directory | Notes |
| --- | --- | --- |
| Web | `apps/web` | Next.js; set `NEXT_PUBLIC_API_URL` |
| API | `apps/api` | FastAPI; set `DATABASE_URL`, `REDIS_URL`, `GEMINI_API_KEY`, `CORS_ORIGINS` |

Before Production API go-live:
1. Provision **Postgres** (Vercel/Neon) and seed listings (`workers/ingest/upsert.py` with `DATABASE_URL` set)
2. Provision **Redis** (Upstash) and set `REDIS_URL` (required — sessions are not durable in-memory on serverless)
3. Set `CORS_ORIGINS` to the web URL; optionally `CORS_ALLOW_VERCEL_PREVIEWS=true`
4. Deploy API → copy URL → set web `NEXT_PUBLIC_API_URL` → redeploy web

## Docs

- `docs/architecture.md` — system design
- `docs/implementation-plan.md` — phase-wise plan
- `docs/superpowers/plans/2026-08-23-vercel-deployment.md` — Vercel deploy plan
- `context.md` — product context

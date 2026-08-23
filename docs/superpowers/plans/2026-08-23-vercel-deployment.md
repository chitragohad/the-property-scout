# Property Scout — Vercel Deployment Plan (Frontend + Backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the Next.js companion UI and FastAPI orchestration API on Vercel as two linked monorepo projects, with production env, CORS, and durable session/listing storage.

**Architecture:** Create **two Vercel projects** from the same Git repo: `property-scout-web` (`apps/web`, Next.js) and `property-scout-api` (`apps/api`, FastAPI ASGI). The web app calls the API via `NEXT_PUBLIC_API_URL`. Listings use **Postgres** (Vercel Postgres / Neon). Conversation sessions must move off the current **in-memory** `SessionStore` to **Redis** (or Postgres) because Vercel Python runs as serverless/Fluid functions (no shared process memory).

**Tech Stack:** Vercel, Next.js 15, pnpm workspaces, FastAPI, SQLAlchemy, Vercel Postgres (or Neon), Upstash Redis (recommended for sessions), Google Gemini API, optional n8n Cloud webhook.

## Global Constraints

- Node.js `>=20`; package manager `pnpm@9.15.0`
- Python `>=3.11` for the API
- Do **not** rely on SQLite file `data/property_scout.db` on Vercel (ephemeral filesystem)
- Do **not** rely on macOS `say` TTS fallback in production (Linux only on Vercel)
- Gemini TTS / turns can exceed default function duration — set `maxDuration` (Hobby: up to 60s; Pro: higher)
- Secrets only in Vercel Environment Variables — never commit `.env`
- CORS must include the production web origin(s)

---

## Why “deploy as-is” will fail

| Current code | Vercel reality | Required change |
| --- | --- | --- |
| `SessionStore` in-process dict (`apps/api/app/services/session_store.py`) | Each invocation can be a different instance | Persist sessions (Redis or Postgres) |
| Default SQLite under `data/` | Disk is ephemeral / not shared | `DATABASE_URL` → Postgres |
| `_macos_say_wav` in `voice.py` | No `say` / `afconvert` on Linux | Gemini-only TTS in prod (or skip TTS gracefully) |
| `CORS_ORIGINS=http://localhost:3000` | Browser blocks cross-origin | Add `https://*.vercel.app` + custom domain |
| Long `/voice/tts` + `/session/.../turn` | Function timeout | Raise `maxDuration`; prefer browser TTS for UX |

**Recommended production shape:**

```
Browser  →  Vercel (Next.js apps/web)
                │  NEXT_PUBLIC_API_URL
                ▼
         Vercel (FastAPI apps/api)
                ├── Postgres (listings)
                ├── Redis (sessions)   ← add before go-live
                ├── Gemini API
                └── n8n webhook (optional)
```

**Alternative (if serverless sessions/timeouts are too painful):** keep **frontend on Vercel**, run **API on Railway / Render / Fly** as a long-lived `uvicorn` process. Same env vars; fewer code changes to `SessionStore`. Prefer this if you need a same-day demo with minimal backend edits.

---

## File map (what will be created / changed)

| File | Responsibility |
| --- | --- |
| `apps/web/vercel.json` (optional) | Web project hints; usually auto-detected |
| `apps/api/vercel.json` | FastAPI entry, `maxDuration`, install/build |
| `apps/api/requirements.txt` or keep `pyproject.toml` | Vercel Python install (pin deps) |
| `apps/api/app/services/session_store.py` | Swap in-memory store for Redis/Postgres |
| `apps/api/app/config.py` | `REDIS_URL`, production CORS helpers |
| `apps/api/app/routers/voice.py` | Disable macOS fallback when not Darwin |
| Root or project env in Vercel Dashboard | Secrets + public URLs |
| Seed / migrate script | Load listings into Postgres once |

---

## Task 1: Prep monorepo for two Vercel projects

**Files:**
- Create: `apps/api/vercel.json`
- Create: `apps/api/requirements.txt` (export from current deps for Vercel Python installer)
- Modify (if needed): root `package.json` / `apps/web` build so Root Directory `apps/web` builds schemas

- [ ] **Step 1: Confirm web builds from monorepo**

```bash
cd "/Users/chitra/Desktop/AI Courses 2026/Nextleap/The Property Scout"
pnpm install
pnpm --filter web build
```

Expected: Next.js build succeeds (workspace `@property-scout/schemas` resolves).

- [ ] **Step 2: Add API `requirements.txt` for Vercel**

From `apps/api`:

```text
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.9.0
pydantic-settings>=2.6.0
sqlalchemy>=2.0.36
google-genai>=1.0.0
python-multipart>=0.0.9
psycopg[binary]>=3.2.0
redis>=5.0.0
```

(`psycopg` / `redis` only after Task 2–3 land.)

- [ ] **Step 3: Add `apps/api/vercel.json`**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": null,
  "installCommand": "pip install -r requirements.txt",
  "functions": {
    "app/main.py": {
      "maxDuration": 60
    }
  }
}
```

Vercel detects FastAPI via `app` in `app/main.py` (already present).

- [ ] **Step 4: Push repo to GitHub/GitLab** (if not already) so Vercel can import it.

- [ ] **Step 5: Commit prep files**

```bash
git add apps/api/vercel.json apps/api/requirements.txt
git commit -m "$(cat <<'EOF'
chore: add Vercel API config and Python requirements

EOF
)"
```

---

## Task 2: Durable listings DB (Postgres)

**Files:**
- Modify: `apps/api/app/config.py` (document `DATABASE_URL`)
- Modify: ingest worker or one-shot seed script to target Postgres
- Vercel / Neon: create Postgres database

- [ ] **Step 1: Provision Postgres**

Options (pick one):
1. **Vercel Storage → Postgres** (Neon-backed) on the API project  
2. **Neon** console → copy connection string  

Use the **pooled** URL for serverless (`?sslmode=require`).

- [ ] **Step 2: Point API at Postgres locally once to verify**

```bash
export DATABASE_URL="postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require"
cd apps/api && .venv/bin/pip install "psycopg[binary]"
.venv/bin/python -c "from app.db.session import init_db; init_db(); print('ok')"
```

- [ ] **Step 3: Seed listings**

Run existing ingest against Postgres:

```bash
cd workers/ingest
# ensure DATABASE_URL is set
../../apps/api/.venv/bin/python upsert.py
```

Verify: `GET /listings?locality=Koramangala&bedrooms=2&max_rent=35000` returns rows.

- [ ] **Step 4: Commit any seed/docs changes; store `DATABASE_URL` only in Vercel env (Production + Preview).**

---

## Task 3: Durable session store (required for Vercel API)

**Files:**
- Modify: `apps/api/app/services/session_store.py`
- Modify: `apps/api/app/config.py` — add `redis_url: str = ""`
- Create: `apps/api/app/services/redis_session_store.py` (or serialize `SessionRecord` into Redis)
- Tests: extend `apps/api/tests/test_session_api.py`

- [ ] **Step 1: Provision Upstash Redis** (Vercel Marketplace or Upstash console). Copy `REDIS_URL` / `UPSTASH_REDIS_REST_URL`.

- [ ] **Step 2: Implement Redis-backed store**

Minimum behavior:
- `create()` → write session JSON/blob with TTL (e.g. 24h)
- `get()` → read + deserialize
- Keep `ConstraintManager` / shortlist serializable (or store `snapshot()` + rebuild)

If full `SessionRecord` (with `EnrichmentService` cache) is hard to pickle, store:
- constraints JSON
- shortlist JSON
- turns, phase, booking, selected_listing_id
- rebuild enrichment cache on demand

- [ ] **Step 3: Wire via settings**

```python
# config
redis_url: str = ""

# get_session_store()
# if settings.redis_url: return RedisSessionStore(...)
# else: return in-memory (local dev)
```

- [ ] **Step 4: Tests**

```bash
cd apps/api && .venv/bin/pytest tests/test_session_api.py -v
```

Expected: PASS with in-memory; optional Redis integration test behind env flag.

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: persist sessions for serverless deployment

EOF
)"
```

---

## Task 4: Production CORS, TTS, and API hardening

**Files:**
- Modify: `apps/api/app/config.py` / CORS usage
- Modify: `apps/api/app/routers/voice.py` — skip `_macos_say_wav` off Darwin (already gated; ensure 502 doesn’t break UX)
- Prefer browser TTS on web (already primary after recent TTS work)

- [ ] **Step 1: CORS**

Set in Vercel API env:

```env
CORS_ORIGINS=https://property-scout-web.vercel.app,https://YOUR_CUSTOM_DOMAIN
```

Include Preview URLs if needed (`https://*-your-team.vercel.app`) or temporarily allow the web project’s pattern carefully.

- [ ] **Step 2: Confirm `/health` and `/voice/config` work without macOS say**

When Gemini is rate-limited, API should return graceful errors; web falls back to `speechSynthesis`.

- [ ] **Step 3: Raise function duration** in `apps/api/vercel.json` (`maxDuration: 60` on Hobby; higher on Pro if Gemini TTS is still used server-side).

---

## Task 5: Create Vercel project — Frontend (`apps/web`)

- [ ] **Step 1: Import repo in Vercel → New Project**

| Setting | Value |
| --- | --- |
| Root Directory | `apps/web` |
| Framework Preset | Next.js |
| Install Command | `cd ../.. && pnpm install` **or** enable monorepo: Install from repo root |
| Build Command | `cd ../.. && pnpm --filter web build` **or** `pnpm build` with root correctly set |
| Output | Next.js default |

**Reliable monorepo pattern:** set Root Directory to `apps/web`, and in Project Settings → General → **Include source files outside Root Directory** / use:

- Install: `pnpm install` from **repository root** (Vercel “Root Directory” + “Override Install Command”: `cd ../.. && pnpm install`)
- Build: `cd ../.. && pnpm --filter web build`

Alternatively use Vercel’s monorepo UI: Root Directory `apps/web`, package manager pnpm detected from root `packageManager`.

- [ ] **Step 2: Env vars (Web project)**

| Name | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://property-scout-api.vercel.app` (set after API URL exists; update + redeploy) |

- [ ] **Step 3: Deploy Preview, open URL, confirm shell loads (API may still show Offline until Task 6).

---

## Task 6: Create Vercel project — Backend (`apps/api`)

- [ ] **Step 1: Second Vercel project from same repo**

| Setting | Value |
| --- | --- |
| Root Directory | `apps/api` |
| Framework | Other / FastAPI (auto) |
| Install | `pip install -r requirements.txt` |

- [ ] **Step 2: Env vars (API project)**

| Name | Required | Notes |
| --- | --- | --- |
| `GEMINI_API_KEY` | Yes | LLM + TTS + STT fallback |
| `DATABASE_URL` | Yes | Postgres URL (`postgresql+psycopg://...`) |
| `REDIS_URL` | Yes (after Task 3) | Session persistence |
| `CORS_ORIGINS` | Yes | Production web URL(s) |
| `LLM_MODEL` | Optional | Prefer a stable text model for serverless, e.g. `gemini-2.5-flash` |
| `GEMINI_TTS_MODEL` | Optional | `gemini-2.5-flash-preview-tts` |
| `GEMINI_VOICE` | Optional | `Charon` |
| `OSM_MODE` | Optional | `overpass` or `static` for demos |
| `N8N_WEBHOOK_URL` | Optional | Shortlist email |
| `LLM_TEMPERATURE` | Optional | `0.2` |
| `LLM_CONFIDENCE_THRESHOLD` | Optional | `0.6` |

- [ ] **Step 3: Deploy and smoke-test**

```bash
curl -s https://YOUR-API.vercel.app/health
# {"status":"ok","n8n_enabled":...}

curl -s https://YOUR-API.vercel.app/voice/config
```

- [ ] **Step 4: Set web `NEXT_PUBLIC_API_URL` to this API URL → **Redeploy web**.

- [ ] **Step 5: Update API `CORS_ORIGINS` to the web production URL → **Redeploy API**.

---

## Task 7: End-to-end production verification

- [ ] **Step 1: Open web URL** → status shows **Connected**

- [ ] **Step 2: Text turn** — e.g. `2 BHK in Koramangala under 40000` → preferences update; voice speaks with text (browser TTS)

- [ ] **Step 3: Confirm Search** → shortlist cards appear

- [ ] **Step 4: Refresh session** mid-flow → session still exists (proves Redis, not memory)

- [ ] **Step 5: Optional email export** if `N8N_WEBHOOK_URL` set

- [ ] **Step 6: Check Vercel Function logs for 429/timeouts on Gemini; increase `maxDuration` or keep browser TTS primary

---

## Task 8: Custom domains & hardening (optional)

- [ ] Add `app.yourdomain.com` → web project; `api.yourdomain.com` → API project  
- [ ] Update `NEXT_PUBLIC_API_URL` + `CORS_ORIGINS`  
- [ ] Lock Preview CORS if needed  
- [ ] Rotate `GEMINI_API_KEY` if it was ever committed  
- [ ] Document runbooks in `README.md` Deploy section (link to this plan)

---

## Deployment checklist (copy/paste)

```text
[ ] Repo on GitHub
[ ] Postgres provisioned + listings seeded
[ ] Redis session store implemented + tested
[ ] apps/api/vercel.json + requirements.txt
[ ] Vercel project: apps/web
[ ] Vercel project: apps/api
[ ] Env vars set on both
[ ] CORS + NEXT_PUBLIC_API_URL cross-linked
[ ] /health OK
[ ] Full voice → search → shortlist demo pass
```

---

## Timeline estimate

| Path | Effort |
| --- | --- |
| **A. Frontend Vercel + API Railway/Render** (keep in-memory + SQLite→Postgres only) | ~2–4 hours |
| **B. Both on Vercel** (Tasks 1–7, including Redis sessions) | ~1–2 days |

---

## Out of scope / later

- CI seed pipeline for listings on every deploy  
- Moving n8n self-host onto Vercel (keep n8n Cloud)  
- Edge runtime for Next.js (not required)  
- Horizontal session affinity (unnecessary once Redis is in place)

---

## Immediate next step

**Path B selected (both on Vercel).** Code prep is in progress:

- [x] `apps/api/vercel.json` + `requirements.txt`
- [x] `apps/web/vercel.json` (pnpm monorepo install/build)
- [x] Redis session store + `store.save()` on mutating routes
- [x] Postgres URL normalization (`postgres://` → `postgresql+psycopg://`)
- [x] CORS preview regex + `.env.example` / README deploy section

**You still need to do in the Vercel dashboard:**
1. Create Postgres + Redis
2. Seed listings against Postgres
3. Create the two Vercel projects and wire env vars (Task 5–6)

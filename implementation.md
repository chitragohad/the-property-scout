# Voice-First AI Property Scout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan phase-by-phase / task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deployed voice-first Bengaluru property scout that completes `PREFERENCES → SEARCH → SHORTLIST → UNDERSTAND → REFINE → COMPARE → BOOK → RECEIVE PDF` with data-grounded explanations (listings + OSM MCP + RAG), never inventing facts.

**Architecture:** Companion web UI talks to an orchestration API that owns session/constraints. Deterministic ranking and hard filters live in code; **Google Gemini** handles NLU/NLG only. Enrichment comes from OpenStreetMap MCP and a cited neighborhood RAG store. Booking is session-local; PDF email goes through n8n. See [`architecture.md`](./architecture.md) and [`context.md`](./context.md).

**Tech Stack:**

| Layer | Choice |
| --- | --- |
| Monorepo | pnpm workspaces (or npm workspaces) |
| Web | Next.js 15 (App Router) + TypeScript + Tailwind |
| API | FastAPI (Python 3.11+) |
| Shared contracts | OpenAPI from FastAPI + `packages/schemas` TypeScript types generated or hand-mirrored |
| Listings / sessions / bookings | PostgreSQL (SQLite acceptable for local MVP) |
| Vector / RAG | Chroma or pgvector |
| LLM | **Google Gemini** (`google-genai` SDK) for intent + extraction + grounded NLG — `LLM_MODEL=gemini-2.5-flash-native-audio-preview-12-2025` (not OpenAI/Anthropic) |
| STT | Browser Web Speech for MVP; optional Google Cloud Speech-to-Text or Gemini multimodal audio for demo polish |
| TTS | Optional (browser `speechSynthesis` or Google Cloud Text-to-Speech) |
| OSM | [open-streetmap-mcp](https://github.com/jagan-shanmugam/open-streetmap-mcp) via MCP client |
| Automation | n8n webhook → PDF → email |
| Tests | pytest (API/domain), Vitest/Playwright (web) |

## Global Constraints

- Never invent neighborhood/POI/listing facts; if unverifiable, say so explicitly.
- Strip all PII (names, phones, emails, agent/owner details) before DB, UI, logs, or Gemini context.
- LLM calls go through **Gemini only** (`GEMINI_API_KEY`, `LLM_MODEL=gemini-2.5-flash-native-audio-preview-12-2025`); do not add OpenAI/Anthropic clients.
- Only **currently available** listings from https://bengaluru.rent/; keep `source_url`.
- Hard constraints exclude; soft preferences only affect ranking.
- Clarification questions: **maximum 5** per discovery session.
- Refinement must **patch** constraints — never full reset unless user asks.
- Shortlist size for primary view: **3–5** listings.
- Demo must show a **real** OSM MCP call and a **real** n8n PDF email.
- Ranking/business scores are **deterministic code**, not Gemini judgment.
- Every neighborhood claim requires a citation (`title`, `url`, `snippet`, `locality`/`topic`).

---

## Target repository layout

```text
apps/
  web/                          # Next.js companion UI
  api/                          # FastAPI orchestration + domain
workers/
  ingest/                       # bengaluru.rent scrape → PII scrub → DB
  rag-index/                    # neighborhood corpus → embeddings
packages/
  schemas/                      # Shared TS types / JSON Schema mirrors
  ranking/                      # Optional: if ranking ever shared; prefer api/app/ranking for MVP
integrations/
  osm-mcp/                      # MCP client wrapper + fixtures
  n8n/                          # workflow JSON + payload examples
docs/                           # existing problem/context/architecture stay at root
```

### Responsibility map

| Path | Owns |
| --- | --- |
| `apps/api/app/schemas/` | Pydantic models: Listing, Constraints, RankResult, Citation, SessionSnapshot, TurnRequest/Response |
| `apps/api/app/services/constraints.py` | Merge patches; hard vs soft; clarification budget |
| `apps/api/app/services/retrieval.py` | Query available listings by hard constraints |
| `apps/api/app/services/ranking.py` | Deterministic score + include/exclude reasons |
| `apps/api/app/services/osm.py` | OSM MCP client; never fabricates POIs |
| `apps/api/app/services/rag.py` | Retrieve cited chunks only |
| `apps/api/app/services/explain.py` | Build evidence bundle → Gemini formats prose |
| `apps/api/app/services/orchestrator.py` | Intent route + pipeline stages |
| `apps/api/app/services/booking.py` | Slots + confirmation codes |
| `apps/api/app/services/export.py` | n8n webhook payload |
| `apps/api/app/routers/session.py` | HTTP surface from architecture §12 |
| `workers/ingest/` | Scrape, filter availability, PII scrub, upsert |
| `workers/rag-index/` | Fetch public sources, chunk, embed, store metadata |
| `apps/web/` | Voice, preferences, shortlist, neighborhood, sources, booking |

---

## Phase overview

| Phase | Name | Outcome (demoable) |
| --- | --- | --- |
| 0 | Foundation | Monorepo boots; health checks; schemas shared |
| 1 | Listings ingestion | Clean available listings in DB with `source_url`, no PII |
| 2 | Constraints + ranking | Textable shortlist from structured prefs (no voice yet) |
| 3 | OSM + RAG enrichment | Shortlist cards have real POIs + cited neighborhood notes |
| 4 | Orchestration + Gemini turns | Text discovery/refine/explain via `/turn` |
| 5 | Companion UI | Full visual companion for session state |
| 6 | Voice I/O | Mic → STT → turn → optional TTS |
| 7 | Booking + n8n | Visit confirmation + emailed PDF |
| 8 | Harden + deploy + demo | Failure paths, deploy, canonical Koramangala walkthrough |

**Rule:** Do not start Phase N+1 until Phase N acceptance criteria pass.

---

## Phase 0 — Foundation

**Goal:** Runnable skeleton with contracts, env, and CI-ready test harness.

### Task 0.1 — Scaffold monorepo

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `apps/web/package.json`
- Create: `apps/api/pyproject.toml`, `apps/api/app/main.py`, `apps/api/app/config.py`
- Create: `.env.example` (include `GEMINI_API_KEY`, `LLM_MODEL=gemini-2.5-flash-native-audio-preview-12-2025`), `README.md` (setup only)
- Create: `packages/schemas/src/index.ts`

- [ ] **Step 1:** Initialize workspaces and empty Next.js + FastAPI apps
- [ ] **Step 2:** Add `GET /health` → `{ "status": "ok" }`
- [ ] **Step 3:** Add web page that fetches `/health` (or shows API URL)
- [ ] **Step 4:** Document `pnpm install`, `uvicorn`, `pnpm dev` in README
- [ ] **Step 5:** Commit `chore: scaffold monorepo foundation`

**Acceptance**
- API health returns 200; web starts without errors.

### Task 0.2 — Core schemas

**Files:**
- Create: `apps/api/app/schemas/listing.py`
- Create: `apps/api/app/schemas/constraints.py`
- Create: `apps/api/app/schemas/ranking.py`
- Create: `apps/api/app/schemas/session.py`
- Create: `apps/api/tests/test_schemas.py`
- Create: `packages/schemas/src/session.ts` (mirror fields)

**Interfaces (produce):**

```python
class HardConstraints(BaseModel):
    bedrooms: int | None = None
    locality: str | None = None
    max_rent: int | None = None
    must_have_amenities: list[str] = []

class SoftPreferences(BaseModel):
    near_metro: bool | None = None
    pet_friendly: bool | None = None
    balcony: bool | None = None

class Constraints(BaseModel):
    hard: HardConstraints = HardConstraints()
    soft: SoftPreferences = SoftPreferences()
    commute_point: str | None = None

class PreferencePatch(BaseModel):
    hard: HardConstraints | None = None
    soft: SoftPreferences | None = None
    commute_point: str | None = None
    patch_mode: Literal["merge"] = "merge"

class RankResult(BaseModel):
    listing_id: str
    score: float
    matched: list[str]
    missing: list[str]
    excluded: bool = False
    exclusion_reasons: list[str] = []
    reason: str

class Citation(BaseModel):
    id: str
    title: str
    url: str
    snippet: str
    locality: str | None = None
    topic: str | None = None
```

- [ ] **Step 1:** Write failing tests that instantiate required listing fields from architecture
- [ ] **Step 2:** Implement Pydantic models including full Listing required fields
- [ ] **Step 3:** Run `pytest apps/api/tests/test_schemas.py -v` → PASS
- [ ] **Step 4:** Commit `feat: add core domain schemas`

**Acceptance**
- Listing requires: `listing_id`, `source_url`, `location`, `locality`, `rent`, `bedrooms`, `furnishing`, `amenities`, `society_name`, `square_footage`, `availability_status`, `latitude`, `longitude`.

---

## Phase 1 — Listings ingestion & privacy

**Goal:** Populate DB with available, scrubbed Bengaluru listings.

### Task 1.1 — PII scrubber

**Files:**
- Create: `workers/ingest/pii.py`
- Create: `workers/ingest/tests/test_pii.py`

- [ ] **Step 1:** Write tests that remove phone/email/name/agent/owner fields and redact patterns in free text
- [ ] **Step 2:** Implement scrubber; ensure scrubbed dict cannot contain forbidden keys
- [ ] **Step 3:** `pytest workers/ingest/tests/test_pii.py -v` → PASS
- [ ] **Step 4:** Commit `feat: pii scrubber for listing ingestion`

**Forbidden keys (minimum):** `owner_name`, `agent_name`, `phone`, `email`, `contact`, `whatsapp`

### Task 1.2 — Ingest pipeline

**Files:**
- Create: `workers/ingest/scrape.py` (fetch/parse bengaluru.rent; keep legal/ToS-aware rate limits)
- Create: `workers/ingest/normalize.py`
- Create: `workers/ingest/upsert.py`
- Create: `apps/api/app/db/` (models + migrations)
- Create: `workers/ingest/tests/test_normalize.py`

- [ ] **Step 1:** Define DB `listings` table matching schema
- [ ] **Step 2:** Filter: keep only currently available; exclude “Not for rent” / equivalents
- [ ] **Step 3:** Normalize amenities to lowercase tokens (`parking`, `balcony`, `pet-friendly`, …)
- [ ] **Step 4:** Always persist `source_url`
- [ ] **Step 5:** Run ingest CLI; verify row count > 0 and spot-check no PII columns
- [ ] **Step 6:** Commit `feat: ingest available listings into db`

**Acceptance**
- Query API or SQL shows available listings only, with lat/lon and `source_url`, zero PII fields.

### Task 1.3 — Listings read API

**Files:**
- Create: `apps/api/app/routers/listings.py`
- Create: `apps/api/app/services/retrieval.py`
- Create: `apps/api/tests/test_retrieval.py`

**Interfaces:**

```python
def find_candidates(constraints: HardConstraints, limit: int = 50) -> list[Listing]:
    """Return available listings matching hard constraints."""
```

- [ ] **Step 1:** Seed test DB with fixture listings (Koramangala 2BHK under/over budget, with/without parking)
- [ ] **Step 2:** Tests for budget, bedrooms, locality, must-have amenity filters
- [ ] **Step 3:** Implement retrieval
- [ ] **Step 4:** Commit `feat: property retrieval by hard constraints`

**Acceptance**
- Hard mismatch never appears in candidates.

---

## Phase 2 — Constraint manager & ranking

**Goal:** Structured preferences → ranked shortlist with persisted reasons (text API only).

### Task 2.1 — Constraint manager

**Files:**
- Create: `apps/api/app/services/constraints.py`
- Create: `apps/api/tests/test_constraints.py`

**Interfaces:**

```python
class ConstraintManager:
    def __init__(self, initial: Constraints | None = None, max_clarifications: int = 5): ...
    def merge(self, patch: PreferencePatch) -> Constraints: ...
    def missing_critical(self) -> list[str]: ...
    def can_ask_clarification(self) -> bool: ...
    def record_clarification(self) -> None: ...
    def is_search_ready(self) -> bool: ...
```

- [ ] **Step 1:** Test merge keeps unrelated fields when only `max_rent` changes
- [ ] **Step 2:** Test clarification counter caps at 5
- [ ] **Step 3:** Test `is_search_ready` requires bedrooms + locality + max_rent (minimum critical set)
- [ ] **Step 4:** Implement and commit `feat: session constraint manager`

### Task 2.2 — Deterministic ranking

**Files:**
- Create: `apps/api/app/services/ranking.py`
- Create: `apps/api/tests/test_ranking.py`

**Score dimensions:** budget, bedrooms, location, must-have amenities, transit proximity, lifestyle prefs, availability.

**Interfaces:**

```python
def rank_listings(
    listings: list[Listing],
    constraints: Constraints,
    enrichment: dict[str, Enrichment] | None = None,
) -> list[RankResult]:
    """Hard-fail → excluded with reasons; soft dims adjust score. Stable sort by score desc."""
```

- [ ] **Step 1:** Fixture: 5 listings; assert hard failures excluded with `exclusion_reasons`
- [ ] **Step 2:** Assert soft prefs change order without excluding
- [ ] **Step 3:** Assert each result has `matched`, `missing`, `reason`
- [ ] **Step 4:** Implement pure functions (no Gemini)
- [ ] **Step 5:** Commit `feat: deterministic listing ranker`

### Task 2.3 — Shortlist service

**Files:**
- Create: `apps/api/app/services/shortlist.py`
- Create: `apps/api/tests/test_shortlist.py`

- [ ] **Step 1:** Build top 3–5 non-excluded results
- [ ] **Step 2:** Persist include + exclude reason sets on session
- [ ] **Step 3:** Drop listings if `availability_status` becomes unavailable
- [ ] **Step 4:** Commit `feat: shortlist builder with reason persistence`

**Phase 2 acceptance**
- Given fixed JSON constraints for Koramangala 2BHK ≤35k + parking, API returns 3–5 scored cards with reasons (enrichment fields may be empty stubs).

---

## Phase 3 — OSM MCP + neighborhood RAG

**Goal:** Real geospatial + cited neighborhood context on shortlist items.

### Task 3.1 — OSM MCP client

**Files:**
- Create: `integrations/osm-mcp/client.py`
- Create: `apps/api/app/services/osm.py`
- Create: `apps/api/tests/test_osm.py` (mock MCP + one optional live test marked `@pytest.mark.integration`)

**Interfaces:**

```python
class OsmPoi(BaseModel):
    name: str
    category: str  # metro|transit|restaurant|school|hospital|grocery|park|other
    lat: float
    lon: float
    distance_m: float | None = None

class OsmContext(BaseModel):
    listing_id: str
    pois: list[OsmPoi]
    raw_call_id: str  # for demo proof / observability
    empty_reason: str | None = None
```

- [x] **Step 1:** Wrap MCP tools for nearby POIs by lat/lon + radius
- [x] **Step 2:** On empty results set `empty_reason` to OpenStreetMap-data framing (never “there is no metro” as absolute invention)
- [x] **Step 3:** Cache by `(listing_id, radius_m)`
- [x] **Step 4:** Integration test or script that prints a real MCP response for one Koramangala coordinate
- [ ] **Step 5:** Commit `feat: openstreetmap mcp enrichment`

### Task 3.2 — RAG corpus + retrieval

**Files:**
- Create: `workers/rag-index/fetch_sources.py`
- Create: `workers/rag-index/chunk_embed.py`
- Create: `apps/api/app/services/rag.py`
- Create: `apps/api/tests/test_rag.py`

**Citation contract:** every hit returns `Citation` fields; no citation → cannot claim. One chunk = one citation (chunk text is the only quotable span).

**Chunking strategy (do not embed listings as documents)**

Three stores stay separate:

| Store | Job |
| --- | --- |
| Listings DB | Exact inventory / ranking (`listings.normalized.json`) |
| OSM MCP | POIs / transit distance |
| RAG index | Cited neighborhood prose only |

Rules for `workers/rag-index/chunk_embed.py`:

1. **Chunk key:** `(locality × topic × source_url)` — never one embedding per listing (Koramangala’s many rows share one guidance blob).
2. **Topics (constrained):** `safety` | `amenities` | `transit` | `lifestyle` | `character` — aligned with `neighborhood_guidance` and UI snapshot sections.
3. **Primary corpus:** fetch public pages for priority localities (Koramangala, HSR, Indiranagar, Whitefield, Jayanagar); **section-aware** splits ~200–400 tokens (not blind fixed windows).
4. **Bootstrap:** optional `origin=seed` chunks from deduped `neighborhood_guidance` text; demote when a real source chunk exists for the same locality+topic.
5. **Dedup:** `hash(locality + topic + canonical_url + normalized_text)` before embed.
6. **Out of index:** rent, BHK, amenities[], gender, deposits, `available_from`, 90-day snapshots, lat/lon, OSM POIs.
7. **Retrieve:** metadata filter (`locality` ± `topic`) first, then vector rank:  
   `retrieve(locality, topic, query, k) -> list[CitedChunk]`

- [x] **Step 1:** Fetch + section-chunk public sources for priority localities; attach citation metadata on every chunk
- [x] **Step 2:** Dedup seed guidance from normalized listings into locality×topic seed chunks (optional bootstrap)
- [x] **Step 3:** Implement `retrieve(locality, topic, query, k) -> list[CitedChunk]` with metadata-then-vector ranking
- [x] **Step 4:** Test: empty index → explicit unverifiable sentinel (no hallucinated text); reject chunks missing `url`/`title`
- [ ] **Step 5:** Commit `feat: neighborhood rag with citations`

### Task 3.3 — Enrichment pipeline hook

**Files:**
- Modify: `apps/api/app/services/shortlist.py` (or new `enrichment.py`)
- Create: `apps/api/tests/test_enrichment_pipeline.py`

```text
candidates
  → OSM per listing (lat/lon)
  → RAG once per unique locality (topics: safety/amenities/transit or soft-pref–inferred)
  → fan out CitedChunk[] to all shortlist cards in that locality
  → attach to shortlist DTOs
```

- [x] **Step 1:** Enrich only after hard filter / before or during soft transit scoring
- [x] **Step 2:** Transit soft score uses OSM data only; neighborhood prose uses RAG citations only
- [x] **Step 3:** Cache RAG hits by locality (and OSM by `listing_id` + radius) for refine turns
- [ ] **Step 4:** Commit `feat: wire osm+rag into shortlist enrichment`

**Phase 3 acceptance**
- Shortlist payload includes POIs from MCP and neighborhood notes with citation URLs; demo script shows MCP `raw_call_id`.
- RAG index has locality×topic chunks (deduped), not one vector per listing; missing RAG still returns the unverifiable sentinel.

---

## Phase 4 — Orchestration, intents, explanations

**Goal:** Conversational `/turn` API that runs the correct pipeline per intent.

### Task 4.1 — Session store + HTTP API

**Files:**
- Create: `apps/api/app/services/session_store.py`
- Create: `apps/api/app/routers/session.py`
- Create: `apps/api/tests/test_session_api.py`

**Endpoints (architecture §12):**

| Method | Path |
| --- | --- |
| `POST` | `/session` |
| `GET` | `/session/{id}` |
| `POST` | `/session/{id}/turn` |
| `POST` | `/session/{id}/confirm-search` |
| `POST` | `/session/{id}/select-listing` |
| `POST` | `/session/{id}/bookings` |
| `POST` | `/session/{id}/export` |

**Turn response must include:** `assistant_text`, `constraints`, `shortlist?`, `citations?`, `booking?`, `phase`

`phase ∈ clarifying | awaiting_confirm | shortlist | booking | ...`

- [x] **Step 1:** Implement create/get session
- [x] **Step 2:** Stub `/turn` echoing text (wire real orchestrator in 4.2)
- [ ] **Step 3:** Commit `feat: session http api`

### Task 4.2 — Intent router + preference extraction (Gemini)

**Files:**
- Create: `apps/api/app/services/gemini.py` (Gemini client wrapper; `google-genai`)
- Create: `apps/api/app/services/intent.py`
- Create: `apps/api/app/services/extract.py`
- Create: `apps/api/tests/test_intent_extract.py`

**Env:** `GEMINI_API_KEY`, `LLM_MODEL` (default `gemini-2.5-flash-native-audio-preview-12-2025`)

**Intents:** `set_preferences`, `clarify_answer`, `confirm_search`, `refine_constraints`, `ask_why`, `compare`, `ask_neighborhood`, `book_visit`, `email_shortlist`, `out_of_scope`

- [x] **Step 1:** Implement `gemini.py` using Google Gen AI SDK (not OpenAI)
- [x] **Step 2:** Prompt extract → `PreferencePatch` JSON only (schema-validated / Gemini structured output)
- [x] **Step 3:** Prompt intent classify → enum only
- [x] **Step 4:** Unit tests with recorded fixtures (no live Gemini required in CI); optional live smoke with `GEMINI_API_KEY`
- [ ] **Step 5:** Commit `feat: gemini intent and preference extraction`

### Task 4.3 — Orchestrator pipelines

**Files:**
- Create: `apps/api/app/services/orchestrator.py`
- Create: `apps/api/tests/test_orchestrator.py`

| Intent | Stages |
| --- | --- |
| discover / confirm_search | retrieve → OSM → RAG → rank → explain → shortlist |
| refine | patch → re-retrieve/re-rank (reuse enrichment cache) |
| explain / compare | read reasons + citations; Gemini formats only |
| clarify | extract + missing_critical; no search |
| book_visit / email_shortlist | dedicated services |

- [x] **Step 1:** Confirmation gate before first search
- [x] **Step 2:** Clarification ≤5
- [x] **Step 3:** Empty matches → suggest relax budget/location
- [x] **Step 4:** Refine test: budget patch keeps bedrooms/locality/parking
- [ ] **Step 5:** Commit `feat: conversation orchestrator pipelines`

### Task 4.4 — Grounded explanation generator

**Files:**
- Create: `apps/api/app/services/explain.py`
- Create: `apps/api/tests/test_explain.py`

- [x] **Step 1:** Build evidence bundle from RankResult + OsmContext + Citations only
- [x] **Step 2:** Gemini prompt forbids claims without citation/listing field IDs
- [x] **Step 3:** Test “why first” returns text that references matched reasons
- [x] **Step 4:** Missing RAG → exact fallback: `I couldn't find reliable public information to verify this.`
- [ ] **Step 5:** Commit `feat: grounded explanation generator via gemini`

**Phase 4 acceptance**
- Scripted text conversation completes: set prefs → confirm → shortlist → why → refine; constraints patch correctly.

---

## Phase 5 — Companion UI

**Goal:** Minimal modern UI that mirrors session truth.

### Task 5.1 — App shell + session hydration

**Files:**
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/components/PreferenceSummary.tsx`
- Create: `apps/web/components/ConversationHistory.tsx`

- [x] **Step 1:** On load `POST /session`, poll/get snapshot
- [x] **Step 2:** Preference panel binds to `constraints`
- [ ] **Step 3:** Commit `feat: web session shell and preference summary`

### Task 5.2 — Shortlist + neighborhood + sources

**Files:**
- Create: `apps/web/components/ShortlistCards.tsx`
- Create: `apps/web/components/NeighborhoodSnapshot.tsx`
- Create: `apps/web/components/SourcesPanel.tsx`

Each card shows: society, locality, rent, bedrooms, area, amenities, availability, match score, why shortlisted.

- [x] **Step 1:** Render 3–5 cards from snapshot
- [x] **Step 2:** Neighborhood + citations per selected card
- [x] **Step 3:** No fabricated empty-state copy beyond API messages
- [ ] **Step 4:** Commit `feat: shortlist neighborhood and sources ui`

### Task 5.3 — Text turn box (pre-voice)

**Files:**
- Create: `apps/web/components/TurnInput.tsx`

- [x] **Step 1:** Submit text to `/turn`; update UI from response diff
- [x] **Step 2:** Show `phase` and assistant response
- [ ] **Step 3:** Commit `feat: text turn input for companion ui`

**Phase 5 acceptance**
- Full discovery/refine/explain usable via typed chat + panels (voice not required yet).

---

## Phase 6 — Voice-first I/O

**Goal:** Primary path is microphone-driven.

### Task 6.1 — STT capture

**Files:**
- Create: `apps/web/components/VoiceControls.tsx`
- Create: `apps/web/lib/stt.ts`
- Optional: `apps/api/app/routers/stt.py` if server-side Google Cloud Speech-to-Text or Gemini multimodal audio

- [x] **Step 1:** Mic button + recording state + live transcript
- [x] **Step 2:** On stop, send transcript as `/turn`
- [x] **Step 3:** Low-confidence / empty → ask repeat
- [ ] **Step 4:** Commit `feat: voice capture and stt turn submission`

### Task 6.2 — Optional TTS

**Files:**
- Create: `apps/web/lib/tts.ts`

- [x] **Step 1:** Speak `assistant_text` after each turn (toggleable)
- [x] **Step 2:** UI text remains source of truth
- [ ] **Step 3:** Commit `feat: optional tts playback`

**Phase 6 acceptance**
- Canonical spoken line works: *“I'm looking for a 2BHK in Koramangala under 35,000. I need parking and I want it close to a metro station.”*

---

## Phase 7 — Booking + n8n PDF email

**Goal:** Close the journey with visit confirmation and emailed shortlist.

### Task 7.1 — Booking service + UI

**Files:**
- Create: `apps/api/app/services/booking.py`
- Modify: `apps/api/app/routers/session.py`
- Create: `apps/web/components/BookingPanel.tsx`
- Create: `apps/api/tests/test_booking.py`

**Interfaces:**

```python
def available_slots(date: date) -> list[str]:
    ...

def confirm_booking(session_id: str, listing_id: str, date: date, slot: str) -> Booking:
    """Returns confirmation_code; persists on session."""
```

- [ ] **Step 1:** Voice/text: “visit Saturday at 4” → offer/confirm slots
- [ ] **Step 2:** UI shows date, slot, confirmation state, code
- [ ] **Step 3:** Commit `feat: site visit booking`

### Task 7.2 — n8n export

**Files:**
- Create: `apps/api/app/services/export.py`
- Create: `integrations/n8n/shortlist_email_workflow.json`
- Create: `integrations/n8n/sample_payload.json`
- Create: `apps/api/tests/test_export.py`

**PDF contents:** preferences, properties (rent/BHK/amenities), match reasoning, neighborhood snapshot, citations, visit info if booked.

- [ ] **Step 1:** Assemble export DTO from session (scrubbed fields only)
- [ ] **Step 2:** `POST` webhook; handle failure without destroying shortlist
- [ ] **Step 3:** Import workflow in n8n; send test email
- [ ] **Step 4:** UI control “Email me this shortlist”
- [ ] **Step 5:** Commit `feat: n8n pdf shortlist email export`

**Phase 7 acceptance**
- Book Saturday 4 PM → code visible; email arrives with PDF containing citations + booking.

---

## Phase 8 — Failure handling, observability, deploy, demo

**Goal:** Production-shaped demo that proves non-negotiables.

### Task 8.1 — Failure copy & degradation

**Files:**
- Modify: orchestrator + UI empty states
- Create: `apps/api/tests/test_failures.py`

| Case | Required behavior |
| --- | --- |
| No matches | Suggest relax budget or location |
| Missing listing fields | Not enough verified information |
| Missing neighborhood | No reliable source |
| No OSM transit | Attribute to available OpenStreetMap data |
| Unavailable listing | Remove from shortlist |
| n8n failure | UI error + retry; keep shortlist |

- [ ] **Step 1:** Implement + test each case
- [ ] **Step 2:** Commit `fix: graceful failure states`

### Task 8.2 — Observability

**Files:**
- Create: `apps/api/app/observability.py`

- [ ] **Step 1:** Structured logs: intent, patches, retrieval counts, OSM `raw_call_id`, RAG hit ids, scores — **no PII**
- [ ] **Step 2:** Optional sources debug panel uses same citation objects
- [ ] **Step 3:** Commit `feat: demo observability traces`

### Task 8.3 — Deploy

**Files:**
- Create: `Dockerfile`, `docker-compose.yml` (api, web, db, optional chroma)
- Update: `README.md` with env vars and deploy steps

- [ ] **Step 1:** Deploy API + web to chosen host (Railway/Fly/Vercel+API)
- [ ] **Step 2:** Ensure OSM MCP and n8n reachable from API
- [ ] **Step 3:** Commit `chore: deployment config`

### Task 8.4 — Canonical demo checklist

- [ ] Mic on → Koramangala 2BHK under 35k + parking + near metro
- [ ] Clarify only if needed (≤5) → confirm
- [ ] Real listings retrieved → OSM MCP called → RAG cited
- [ ] 3–5 shortlist cards with scores + why
- [ ] “Why did you pick the first one?” → grounded + sources visible
- [ ] “Drop anything above 32K and show me something pet-friendly.” → partial update only
- [ ] Select property → “visit Saturday at 4” → confirmation code
- [ ] “Email me this shortlist” → n8n PDF received

- [ ] Record short demo notes / screenshots of MCP call + email
- [ ] Commit `docs: demo verification notes` (if notes file added)

**Phase 8 acceptance = project success criteria from context.md**

---

## Testing strategy (all phases)

| Layer | Tool | Focus |
| --- | --- | --- |
| Domain | pytest | constraints merge, ranking math, PII scrub, retrieval filters |
| API | pytest + httpx | session turns, refine patches, export payload |
| Integration | marked tests | live OSM MCP, live Gemini optional |
| UI | Playwright | voice button states, shortlist render, booking panel |
| Manual | Demo script | Full Koramangala journey on deployed URL |

**TDD preference for domain packages:** ranking, constraints, PII, retrieval — write failing tests first in those tasks.

---

## Suggested milestone timeline (indicative)

| Week | Phases |
| --- | --- |
| 1 | 0–1 Foundation + ingestion |
| 2 | 2–3 Ranking + OSM/RAG |
| 3 | 4–5 Orchestration + UI |
| 4 | 6–8 Voice + booking + n8n + deploy + demo |

Adjust to team size; keep phase exit criteria strict.

---

## Spec coverage matrix

| Context / architecture requirement | Phase |
| --- | --- |
| Available listings + `source_url` + PII scrub | 1 |
| Hard vs soft + deterministic ranking + reasons | 2 |
| Real OSM MCP (no invented POIs) | 3 |
| RAG citations / no Gemini neighborhood invention | 3–4 |
| Intent routing, ≤5 clarifications, confirm gate | 4 |
| Incremental refine + session memory | 4 |
| Companion UI modules A–F | 5–7 |
| Voice-first STT path | 6 |
| Site visit booking | 7 |
| n8n PDF email | 7 |
| Failure states + never invent | 8 |
| Deployed end-to-end demo | 8 |

---

## Out of scope (explicit YAGNI)

- Multi-city support beyond Bengaluru
- User accounts / long-term auth (session-only is enough for demo)
- Payments or real broker scheduling integrations
- Training custom speech models
- Replacing deterministic ranker with Gemini-as-judge
- OpenAI / Anthropic LLM clients (Gemini is the sole LLM provider)

---

## Document map

| Doc | Role |
| --- | --- |
| [`problemStatement.md`](./problemStatement.md) | Full requirements |
| [`context.md`](./context.md) | Compressed product context |
| [`architecture.md`](./architecture.md) | System design |
| `implementation.md` (this file) | Phase-wise build plan |

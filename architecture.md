# Architecture — Voice-First AI Property Scout

> Derived from [`problemStatement.md`](./problemStatement.md) and [`context.md`](./context.md).  
> This document defines **how** the system is structured so the product can deliver lifestyle-fit property discovery with verifiable data.

---

## 1. Goals & architectural principles

### Product goal

A deployed **voice-first** assistant for Bengaluru renters/buyers that:

1. Captures spoken preferences
2. Retrieves **real, currently available** listings
3. Enriches them with **real geospatial + RAG** neighborhood context
4. Ranks transparently (hard vs soft constraints)
5. Explains shortlists with **citations**
6. Supports incremental voice refinement
7. Books site visits
8. Emails a PDF shortlist via **n8n**

### Non-negotiable principles

| Principle | Architectural implication |
| --- | --- |
| Lifestyle fit over listing dump | Enrichment + ranking + explanation are first-class pipelines, not UI afterthoughts |
| Data-grounded, never invent | Facts come from listings DB, OSM MCP, and RAG store — never from Gemini parametric knowledge |
| Transparent reasoning | Every include/exclude produces a persisted reason object |
| Incremental refinement | Constraint manager is the single source of truth for preferences; search is re-run against patched constraints |
| Privacy by default | PII stripped at ingestion; never enters DB, UI, logs, or Gemini context |
| Deterministic where it matters | Ranking/scoring and hard filters are code; Gemini handles language only |
| Voice-first, UI-companion | Conversation orchestrator owns turn state; UI mirrors session state |

### Core question the system must always answer

> Why should I consider this property?

---

## 2. System context

```text
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│   User      │────▶│  Companion Web App   │────▶│  Orchestration API  │
│ (voice+UI)  │◀────│  (mic, shortlist,    │◀────│  (session, intents, │
└─────────────┘     │   booking, sources)  │     │   pipeline runner)  │
                    └──────────────────────┘     └──────────┬──────────┘
                                                            │
          ┌─────────────────┬─────────────────┬─────────────┼──────────────┐
          ▼                 ▼                 ▼             ▼              ▼
   ┌────────────┐   ┌────────────┐   ┌────────────┐  ┌──────────┐  ┌──────────┐
   │ STT / TTS  │   │ Gemini LLM │   │ Listings   │  │ OSM MCP  │  │ RAG      │
   │ providers  │   │ (NLU / NLG)│   │ store      │  │ (POIs)   │  │ store    │
   └────────────┘   └────────────┘   └────────────┘  └──────────┘  └──────────┘
                                                            │
                                                            ▼
                                                   ┌────────────────┐
                                                   │ n8n workflow   │
                                                   │ PDF → Email    │
                                                   └────────────────┘
```

### External systems

| System | Role | Constraint |
| --- | --- | --- |
| [bengaluru.rent](https://bengaluru.rent/) | Source of property listings | Scrape/import only **available** listings; keep `source_url`; strip PII |
| [OpenStreetMap MCP](https://github.com/jagan-shanmugam/open-streetmap-mcp) | Nearby transit & POIs | Mandatory; demo must show a real MCP call; no invented places |
| Public web sources (Wikipedia, guides) | Neighborhood RAG corpus | Cite title, URL, snippet, locality/topic |
| **Google Gemini** (LLM) | Intent classification, preference extraction, grounded NLG explanations | Use Gemini API (`google-genai` / Gemini Developer API); never use model knowledge for neighborhood/POI facts |
| Speech-to-Text / Text-to-Speech | Voice I/O | Prefer low latency; browser Web Speech for MVP, or Google Cloud Speech / Gemini multimodal audio for polish |
| n8n | PDF generation + email | Demonstrable webhook-triggered workflow |

---

## 3. High-level pipeline

Canonical processing path from the problem statement:

```text
VOICE INPUT
    ↓
Speech-to-Text
    ↓
Conversation / Intent Layer
    ↓
Preference Extraction
    ↓
Constraint Manager
    ↓
Property Retrieval
    ↓
OpenStreetMap MCP
    ↓
Neighborhood RAG
    ↓
Ranking Engine
    ↓
Explanation Generator
    ↓
Shortlist
    ↓
Voice Response + UI
    ↓
Site Visit Booking
    ↓
n8n → PDF Generation → Email
```

Not every user turn runs the full pipeline. The **intent layer** routes turns:

| Intent family | Pipeline stages run |
| --- | --- |
| `discover` / `confirm_search` | Full: retrieve → OSM → RAG → rank → explain → shortlist |
| `refine` | Patch constraints → re-retrieve/re-rank (reuse enrichment cache where possible) |
| `explain` / `compare` | Read shortlist + reason store + citations; Gemini formats answer only |
| `book_visit` | Booking service only |
| `email_shortlist` | n8n trigger only |
| `clarify` | Preference extraction + constraint gaps; no search yet |

---

## 4. Logical architecture (layers)

```text
┌─────────────────────────────────────────────────────────────┐
│ Presentation                                                │
│  Voice controls · Preference panel · Shortlist · Sources ·  │
│  Neighborhood snapshot · Booking panel                      │
└────────────────────────────┬────────────────────────────────┘
                             │ WebSocket / HTTPS (session events)
┌────────────────────────────▼────────────────────────────────┐
│ Application / Orchestration                                 │
│  Session manager · Intent router · Turn policy              │
│  Clarification policy (≤5) · Confirmation gate              │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│ Domain services                                             │
│  Preference extractor · Constraint manager · Retrieval      │
│  Enrichment (OSM + RAG) · Ranking · Explanation · Booking   │
│  Shortlist service · Export (n8n)                           │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│ Intelligence adapters                                       │
│  STT/TTS · Gemini LLM client · OSM MCP client · Vector/RAG client  │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│ Data                                                        │
│  Listings DB · Session store · Reason/audit store           │
│  Embedding index · Booking store · Ingestion/PII scrubber   │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Component design

### 5.1 Companion UI (presentation)

**Purpose:** Minimal modern companion to voice — mirrors session truth, never invents facts.

| Module | Responsibility |
| --- | --- |
| Voice interaction | Mic button, recording state, live transcript, assistant response, conversation history |
| Preference summary | Location, budget, bedrooms, must-haves, soft preferences, commute point |
| Shortlist cards | Society, locality, rent, bedrooms, area, amenities, availability, match score, why shortlisted |
| Neighborhood snapshot | Transit, nearby amenities, practical notes, citations |
| Sources / references | Citations for neighborhood, transit, amenity claims |
| Visit booking | Preferred date, slots, confirmation state, confirmation code |

**UI principles**

- Conversational, trustworthy, transparent, fast, minimal, data-grounded
- Avoid generic chat clutter, long paragraphs, unsupported claims, feature overload
- Every card should make “why consider this?” scannable

### 5.2 Speech layer (STT / TTS)

```text
Mic audio → STT → transcript text → Orchestrator
Orchestrator reply text → TTS → audio playback (optional) + UI text
```

- STT output is the durable turn input (also shown as live transcript)
- TTS is optional enhancement; UI text remains authoritative for accessibility

### 5.3 Conversation / intent layer

**Purpose:** Classify each turn and decide whether to clarify, confirm, search, refine, explain, book, or export.

**Suggested intents**

| Intent | Examples |
| --- | --- |
| `set_preferences` | “2BHK in Koramangala under 35k with parking near metro” |
| `clarify_answer` | User answering a clarification question |
| `confirm_search` | Affirmative after preference confirmation |
| `refine_constraints` | “Drop anything above 32k”, “show pet-friendly” |
| `ask_why` | “Why did you pick the first one?” |
| `compare` | “Why is this better than the other?” |
| `ask_neighborhood` | “What’s this neighborhood like?” |
| `book_visit` | “Visit Saturday at 4” |
| `email_shortlist` | “Email me this shortlist” |
| `out_of_scope` | Unrelated request |

**Clarification policy**

- Ask only when a **critical** field is missing for a meaningful search
- Hard cap: **maximum 5** clarification questions per discovery session
- Prefer confirming a complete-enough constraint set over exhaustive questioning

**Confirmation gate**

Before first search (and after material refine if needed), emit a confirmation utterance, e.g.:

> Got it. You're looking for a 2BHK in Koramangala under ₹35,000/month, with parking and convenient access to a metro station…

### 5.4 Preference extraction (Gemini-assisted)

**Provider:** Google **Gemini** via `LLM_MODEL=gemini-2.5-flash-native-audio-preview-12-2025` (native audio–capable Flash preview; suitable for low-latency voice + NLU/NLG turns).

**Gemini owns:** parsing natural language into structured preference deltas (prefer JSON / structured output mode).  
**Does not own:** deciding hard vs soft policy weights, inventing amenities, inventing locations.

**Output shape (illustrative)**

```json
{
  "hard": {
    "bedrooms": 2,
    "locality": "Koramangala",
    "max_rent": 35000,
    "must_have_amenities": ["parking"]
  },
  "soft": {
    "near_metro": true,
    "pet_friendly": null,
    "balcony": null
  },
  "commute_point": null,
  "uncertain_fields": [],
  "patch_mode": "merge"
}
```

For refinements, extractor returns a **patch** (`patch_mode: "merge"`), not a full replacement — unless the user explicitly resets.

### 5.5 Constraint manager (session source of truth)

**Purpose:** Own the current preference state for the session.

Responsibilities:

- Merge preference patches into session constraints
- Classify fields as hard vs soft
- Track clarification count and remaining budget
- Expose “searchable?” readiness
- Never drop unrelated constraints on a partial update

**Example merge**

```text
Before: 2BHK + Koramangala + ₹35K + parking
User:   "Increase budget to ₹40K"
After:  2BHK + Koramangala + ₹40K + parking
```

### 5.6 Property retrieval

**Input:** hard constraints (+ optional soft for candidate broadening strategy).  
**Source:** local listings store populated from bengaluru.rent (ingestion separate from request path).

**Rules**

- Only `availability_status` indicating currently available
- Exclude “Not for rent” / transparency-only
- Always retain `source_url` / `listing_id` for traceability
- If no candidates: return structured empty result → orchestrator suggests relaxing budget or location

### 5.7 Enrichment — OpenStreetMap MCP

**Mandatory integration.** Demo must prove a real MCP call.

```text
listing (lat, lon)
    → OSM MCP nearby query
    → transit points, metro, restaurants, schools, hospitals, grocery, parks, other POIs
    → structured neighborhood context attached to listing
```

**Rules**

- Never invent POIs
- If empty: surface “couldn’t find nearby transit/POI in available OpenStreetMap data”
- Cache enrichment by `listing_id` + radius/params for refine turns

### 5.8 Enrichment — Neighborhood RAG

**Purpose:** Practical neighborhood guidance grounded in public sources.

**Retrieve for:** character, public safety info, lifestyle, transit character, amenities context, local descriptions.

#### Three stores, three jobs (do not conflate)

| Store | Responsibility | Not for |
| --- | --- | --- |
| Listings DB (`listings.normalized.json` ingest) | Exact inventory + hard/soft ranking fields | Neighborhood prose retrieval |
| OSM MCP | POIs / transit distance by lat/lon | Lifestyle narrative or citations |
| RAG index | Cited neighborhood prose only | Rent, BHK, amenities arrays, snapshot history |

`listings.normalized.json` is **inventory**, not the primary RAG corpus. Listing facts stay in SQL; OSM stays on MCP; vectors hold only citeable neighborhood text.

#### Chunking strategy — `(locality × topic × source)`

Chunk by locality and topic, **not by listing**. One atomic chunk per topic per locality per source URL (e.g. `koramangala:safety`, `hsr-layout:transit`).

Allowed `topic` values (constrained): `safety` | `amenities` | `transit` | `lifestyle` | `character`.

This matches the existing seed shape in normalized listings (`neighborhood_guidance.safety` / `.amenities` / `.transit_character`) and maps cleanly to voice intents (`ask_neighborhood`, safety, metro, groceries).

**Primary corpus:** fetch public pages from citation URLs (Wikipedia / curated Bengaluru guides), then split with **section-aware** chunks (~200–400 tokens), not blind fixed-size splits.

**Bootstrap only:** current `neighborhood_guidance` prose may be indexed as `origin=seed` chunks with the same schema, lower priority once a real source chunk exists for that locality+topic.

**Deduplicate at index time:** key = `hash(locality + topic + canonical_url + normalized_text)`. Many listings share one locality (e.g. eight Koramangala rows) → a few locality chunks, not one embedding per listing.

**Do not embed:** whole listing JSON; rent/deposit/BHK/amenities/gender/`available_from`; 90-day snapshot series; lat/lon or POI lists. Mixing structured filters into vectors turns hard constraints into noisy semantic search.

#### Citation contract (one citation = one chunk)

**Each chunk/citation must retain**

- `title`
- `url`
- `snippet` / content reference
- `locality` / `topic`
- optional: `section_heading`, `fetched_at`, `origin` (`source` | `seed`)

**Rules**

- Chunk text = only text Gemini may quote; metadata = Sources panel payload
- No chunk without `url` + `title` → must not be returned by retrieve
- Every neighborhood claim in NL explanations must map to a citation ID
- If retrieval fails: “I couldn't find reliable public information to verify this.”
- Gemini must not fill gaps with general knowledge

#### Retrieval pattern

```text
Filter metadata first (locality ± topic), then vector-rank within that set.
retrieve(locality, topic?, query, k) → list[CitedChunk]

Shortlist enrichment:
  For each unique shortlist locality (once):
    RAG topics safety/amenities/transit (or inferred from soft prefs)
    attach CitedChunk[] → fan out to all cards in that locality
  For each listing:
    OSM nearby(lat, lon, radius)  # separate path
```

### 5.9 Ranking engine (deterministic)

**Purpose:** Transparent scoring; separate hard filters from soft preference scoring.

**Hard constraints (normally exclude on fail)**

- Bedrooms, locality/location match, max rent, must-have amenities, availability

**Soft preferences (affect score)**

- Near metro / transit proximity, balcony, pet-friendly, other lifestyle prefs

**Suggested score dimensions**

1. Budget match  
2. Bedroom match  
3. Location match  
4. Must-have amenities  
5. Transit proximity (from OSM)  
6. Lifestyle preferences  
7. Availability  

**Output per candidate**

```json
{
  "listing_id": "ABC",
  "score": 87,
  "matched": ["2BHK", "within budget", "parking", "near transit"],
  "missing": ["balcony"],
  "excluded": false,
  "exclusion_reasons": [],
  "reason": "Strong match for all mandatory requirements."
}
```

Persist include **and** exclude reasons for “why didn’t you pick this?” queries.

**Shortlist size:** produce **3–5** listings for the primary shortlist view.

### 5.10 Explanation generator

**Inputs (tools/facts only):** listing fields, rank reason objects, OSM context, RAG citations.  
**Gemini role:** turn structured evidence into concise spoken/UI prose — **no new facts**.

Must support:

- Why this one?
- Why not that one?
- Why better than the other?
- Is commute realistic? (only if commute point + data exist)
- What’s the neighborhood like? (cited)
- Metro access? (OSM-backed)
- Within budget? (listing rent vs constraint)

### 5.11 Shortlist service

Owns the active shortlist for the session:

- Ordered ranked listings
- Attached enrichment + citations
- Reason payloads
- Selection state (which property user “likes” for booking)

On refine: rebuild shortlist from updated constraints; drop unavailable listings.

### 5.12 Site visit booking

Voice-negotiated slots with UI reflection.

```text
User selects listing → requests day/time
  → Booking service offers available slots
  → User picks slot
  → Confirmation code generated
  → UI shows date, slot, confirmed state, code
```

Booking store is independent of ranking facts; confirmation code is session-durable for the demo.

### 5.13 n8n export pipeline

```text
UI/voice "Email me this shortlist"
  → Orchestrator POST webhook to n8n
  → n8n formats payload
  → Generate PDF
  → Email user
```

**PDF must include**

- User preferences  
- Shortlisted properties (rent, bedrooms, amenities)  
- Match reasoning  
- Neighborhood snapshot  
- Sources/citations  
- Site visit info if booked  

Workflow must be demonstrable end-to-end.

---

## 6. Gemini vs deterministic boundary

**LLM provider:** Google Gemini only (not OpenAI / Anthropic). Configure via `GEMINI_API_KEY` and `LLM_MODEL=gemini-2.5-flash-native-audio-preview-12-2025` (or Vertex AI credentials in production).

| Use Gemini | Do **not** use Gemini |
| --- | --- |
| Conversational understanding / intent | Factual neighborhood claims |
| Preference extraction & clarification phrasing | Inventing POIs / amenities / transit |
| Natural language explanations from evidence | Hard filter decisions & numeric scores (prefer code) |
| Voice response phrasing | “Filling in” missing OSM/RAG data |

```text
                    ┌──────────────────────┐
   User language ──▶│ Gemini (NLU / NLG)   │
                    └──────────┬───────────┘
                               │ structured intents / patches / prose requests
                    ┌──────────▼───────────┐
                    │ Domain services      │◀── Listings / OSM / RAG / Ranker
                    │ (truth & decisions)  │
                    └──────────────────────┘
```

---

## 7. Data architecture

### 7.1 Listing schema (required fields)

| Field | Notes |
| --- | --- |
| `listing_id` | Stable unique ID |
| `source_url` | Traceable link to original listing |
| `location` | Coarse location string |
| `locality` | Neighborhood / locality |
| `rent` | Numeric rent |
| `bedrooms` | Bedroom count |
| `furnishing` | Furnishing status |
| `amenities` | Normalized amenity list |
| `society_name` | Building/society (non-PII) |
| `square_footage` | Area |
| `availability_status` | Must indicate currently available for search |
| `latitude` / `longitude` | Required for OSM enrichment |

### 7.2 Ingestion & PII scrubbing

```text
Scrape/import bengaluru.rent
    → Filter availability
    → PII scrubber (names, phones, emails, agent/owner details)
    → Normalize amenities / localities
    → Upsert listings store
```

**Hard rule:** PII never enters database, application, UI, logs, or Gemini context.

### 7.3 Session model (conceptual)

| Entity | Contents |
| --- | --- |
| `Session` | id, created_at, clarification_count, phase |
| `Constraints` | hard + soft preference maps, commute_point |
| `ConversationTurn[]` | role, transcript, intent, timestamp |
| `Shortlist` | ordered listing_ids, scores, reasons |
| `EnrichmentCache` | listing_id → OSM + RAG payloads |
| `Citations[]` | id, title, url, snippet, locality/topic, claim_ids |
| `Booking` | listing_id, date, slot, status, confirmation_code |

### 7.4 RAG corpus

- Index unit: `(locality × topic × source_url)` — not per listing
- Primary docs: fetched public sources; seed guidance from ingest is bootstrap-only and deduped by locality
- Section-aware chunks (~200–400 tokens) with citation metadata on every row
- Metadata mirrors citation requirements (`title`, `url`, `snippet`, `locality`, `topic`, …)
- Retrieve with metadata filter then vector rank; return chunks **with** citation metadata; generation may only use returned chunks
- Listings DB + OSM cache remain separate from the vector index

---

## 8. Key sequence flows

### 8.1 Discovery (first search)

```text
User mic → STT transcript
  → Intent: set_preferences
  → Extract preferences → Constraint manager merge
  → If gaps: clarify (≤5) → wait
  → Confirm constraints aloud + UI preference panel
  → On confirm:
       Retrieve available listings
       For top candidates: OSM MCP + RAG
       Rank (hard filter + soft score)
       Persist reasons (include/exclude)
       Build shortlist (3–5)
       Explanation summaries for cards
  → TTS/UI: present shortlist + sources
```

### 8.2 Explain

```text
User: "Why did you pick the first one?"
  → Intent: ask_why
  → Load shortlist[0] reason + OSM + RAG citations
  → Gemini formats grounded answer (citation IDs only)
  → UI highlights sources
```

### 8.3 Refine (partial update)

```text
User: "Drop anything above 32K and show me something pet-friendly."
  → Intent: refine_constraints
  → Patch: max_rent=32000, soft.pet_friendly=true
  → Do NOT reset unrelated constraints
  → Re-run retrieval/rank (reuse enrichment cache)
  → Update shortlist + preference panel + voice summary of what changed
```

### 8.4 Book + email

```text
User selects listing + "visit Saturday at 4"
  → Booking service validates slot → confirmation code → UI update

User: "Email me this shortlist"
  → Assemble export DTO (prefs, shortlist, reasons, neighborhood, citations, booking)
  → n8n webhook → PDF → email
```

---

## 9. Failure & degradation architecture

| Failure | System behavior |
| --- | --- |
| No matching listings | Empty shortlist + suggest relaxing budget or location |
| Missing listing fields for a requirement | “This listing doesn't have enough verified information…” — do not invent |
| Missing neighborhood RAG | Explicit unverifiable message; no Gemini filler |
| No OSM transit/POI | Attribute gap to available OpenStreetMap data |
| Listing becomes unavailable | Remove from active shortlist |
| STT low confidence | Ask user to repeat or confirm transcript in UI |
| OSM/RAG provider timeout | Continue with partial enrichment; mark missing sections honestly |
| n8n/email failure | Surface failure in UI; keep shortlist intact for retry |

**Global rule:** never pretend to know something that cannot be verified.

---

## 10. Privacy & security architecture

```text
Ingestion boundary
  ┌──────────────────────────────────────────┐
  │ Raw scrape  →  PII scrubber  →  Clean   │
  │ (ephemeral)     (mandatory)     records │
  └──────────────────────────────────────────┘
         │
         ▼
   Listings DB / Gemini prompts / logs / UI  ← only clean records
```

Controls:

- Allowlist listing fields into Gemini prompts
- Redact logs at write time
- Do not store owner/agent contact channels at all
- Export PDF uses the same scrubbed shortlist DTO

---

## 11. Suggested repository / service topology

Compatible with a single deployable app + workers (exact stack flexible):

| Unit | Responsibility |
| --- | --- |
| `web/` | Companion UI |
| `api/` | Orchestration, session, domain services |
| `workers/ingest/` | Scrape/normalize/PII scrub → listings DB |
| `workers/rag-index/` | Build/update neighborhood embeddings |
| `integrations/osm-mcp/` | MCP client wrapper |
| `integrations/n8n/` | Webhook payload contracts + workflow JSON |
| `packages/ranking/` | Deterministic scoring (unit-test heavy) |
| `packages/schemas/` | Shared Zod/JSON schemas for constraints, reasons, citations |

---

## 12. API surface (logical)

Illustrative contracts — implement as REST, RPC, or WS events:

| Endpoint / event | Purpose |
| --- | --- |
| `POST /session` | Create session |
| `POST /session/{id}/turn` | Submit transcript or text turn; returns assistant message + state diff |
| `GET /session/{id}` | Full session snapshot for UI hydration |
| `POST /session/{id}/confirm-search` | Explicit confirm if not done via voice |
| `POST /session/{id}/select-listing` | Mark listing for booking focus |
| `POST /session/{id}/bookings` | Create/confirm visit |
| `POST /session/{id}/export` | Trigger n8n email |

**Turn response should include**

- Assistant text
- Updated constraints
- Shortlist (if changed)
- Citations (if any)
- Booking (if any)
- UI phase hints (`clarifying` | `awaiting_confirm` | `shortlist` | `booking` | …)

---

## 13. Observability (demo-friendly)

To prove grounding in demos/evals:

- Log structured events: intent, constraint patches, retrieval counts, OSM call IDs, RAG hit IDs, rank scores
- **Never** log PII
- Expose a debug/sources panel fed by the same citation objects shown to users
- Persist sample traces for the canonical Koramangala demo path

---

## 14. Deployment view

```text
                  ┌──────────────┐
 User browsers ──▶│ Web app CDN  │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐     ┌─────────────┐
                  │ API service  │────▶│ Session DB  │
                  └──────┬───────┘     │ Listings DB │
           ┌─────────────┼─────────────┤ Vector DB   │
           ▼             ▼             └─────────────┘
     ┌──────────┐  ┌──────────┐
     │ Gemini   │  │ OSM MCP  │
     │ + STT    │  │ server   │
     └──────────┘  └──────────┘
           │
           ▼
     ┌──────────┐
     │ n8n      │──▶ PDF storage / SMTP
     └──────────┘
```

Ingestion and RAG indexing can run as scheduled jobs separate from the request path so voice turns stay fast.

---

## 15. Architecture success criteria

The architecture is correct when:

1. A user can complete **PREFERENCES → SEARCH → SHORTLIST → UNDERSTAND → REFINE → COMPARE → BOOK → RECEIVE PDF** primarily by voice  
2. Every factual recommendation is traceable to listings, OSM, or RAG citations  
3. Refinement patches constraints without resetting the session  
4. Ranking/exclusion reasons are persisted and queryable  
5. PII never crosses the scrubber boundary  
6. The demo exhibits a **real** OpenStreetMap MCP call and a **real** n8n PDF email  

---

## 16. Document map

| Doc | Role |
| --- | --- |
| [`problemStatement.md`](./problemStatement.md) | Full product requirements |
| [`context.md`](./context.md) | Compressed working context |
| `architecture.md` (this file) | System structure, boundaries, and flows |

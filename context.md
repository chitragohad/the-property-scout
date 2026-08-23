# Project Context — Voice-First AI Property Scout

> Source of truth: [`problemStatement.md`](./problemStatement.md)

This file is the compressed working context for building the product. Prefer this for agent/dev orientation; use `problemStatement.md` for full detail.

---

## One-line summary

Deployed **voice-first AI property discovery assistant for Bengaluru** that finds real listings from spoken preferences, evaluates lifestyle fit with real geospatial + RAG data, explains shortlists with citations, refines by voice, books site visits, and emails a PDF via n8n.

## Core principle

**Don't just help users find properties. Help them understand whether a property actually fits their life.**

Never invent facts. If data is missing, say so clearly.

---

## Problem being solved

Listings are easy to find; lifestyle fit is hard to judge (commute, transit, neighborhood, amenities, trade-offs, why A over B). Answers must come from **real data**, not generic LLM knowledge.

---

## End-to-end user journey

```text
PREFERENCES → SEARCH → SHORTLIST → UNDERSTAND → REFINE → COMPARE → BOOK → RECEIVE PDF
```

### Canonical demo (must work)

1. Mic on → voice: 2BHK Koramangala under ₹35k, parking, near metro
2. Extract → clarify (max 5) → confirm
3. Fetch available listings → filter/rank
4. OpenStreetMap MCP for POIs/transit → RAG for neighborhood notes
5. Show **3–5** shortlist cards with scores + reasons + citations
6. Voice: “Why the first one?” → grounded answer + UI sources
7. Voice: “Drop above 32K + pet-friendly” → **partial** constraint update only
8. Voice book Saturday 4 PM → confirmation code in UI
9. “Email me this shortlist” → n8n PDF → email

---

## Product capabilities (must-have)

| # | Capability |
| --- | --- |
| 1 | Real currently available Bengaluru listings |
| 2 | Real neighborhood / geospatial data (OSM MCP) |
| 3 | Voice-first conversation |
| 4 | RAG-grounded explanations with citations |
| 5 | Transparent shortlist include/exclude reasons |
| 6 | Voice shortlist refinement (incremental) |
| 7 | Site-visit booking by voice |
| 8 | n8n → PDF shortlist → email |

---

## Voice UX rules

- Primary interaction = voice
- Extract: location, bedrooms, budget, must-haves, soft preferences
- Clarify only when needed; **≤ 5** clarification questions
- Confirm constraints before search
- Session memory: never re-ask known preferences; merge incremental requests
- Refinement: change **only the affected constraint**; keep the rest

---

## Data & integrations

### Listings — https://bengaluru.rent/

- Only **currently available** listings
- Exclude “Not for rent” / transparency-only status
- Keep traceable `source_url`

**Required fields:** `listing_id`, `source_url`, `location`, `locality`, `rent`, `bedrooms`, `furnishing`, `amenities`, `society_name`, `square_footage`, `availability_status`, `latitude`, `longitude`

### OpenStreetMap MCP (mandatory)

- Repo: https://github.com/jagan-shanmugam/open-streetmap-mcp
- Nearby metro/transit, restaurants, schools, hospitals, grocery, parks, other POIs
- **Do not invent POIs**; demo must show a real MCP call

### Neighborhood RAG

- Character, safety (public info), lifestyle, transit, amenities, local descriptions
- Sources: Wikipedia, city/neighborhood guides, other trustworthy public sources
- Each source retains: title, URL, snippet/reference, locality/topic
- Every neighborhood claim needs a citation
- No LLM general knowledge for unsupported claims
- Fallback: “I couldn't find reliable public information to verify this.”

### Privacy

Strip all PII before DB / app / UI / logs / LLM: names, phones, emails, agent/owner details. Never display or log PII.

---

## Ranking & reasoning

### Hard vs soft

| Type | Effect | Examples |
| --- | --- | --- |
| Hard constraints | Fail → usually exclude | 2BHK, Koramangala, ≤ ₹35K, parking |
| Soft preferences | Affect score/rank | Near metro, balcony, pet-friendly |

### Score dimensions

Budget · bedrooms · location · must-have amenities · transit proximity · lifestyle prefs · availability

### Explanation contract

- Every include/exclude has a stored reason
- Answer “why this / why not / why better / commute / neighborhood / metro / budget”
- Cite OSM / RAG / listing fields; no vague praise (“great neighborhood”)

Example reason payload shape:

```json
{
  "listing": "ABC",
  "score": 87,
  "matched": ["2BHK", "within budget", "parking", "near transit"],
  "missing": ["balcony"],
  "reason": "Strong match for all mandatory requirements."
}
```

---

## Companion UI (minimal, modern)

| Block | Must show |
| --- | --- |
| Voice | Mic, recording state, live transcript, response, history |
| Preferences | Location, budget, bedrooms, must-haves, preferences, commute point |
| Shortlist cards | Society, locality, rent, BHK, area, amenities, availability, score, why shortlisted |
| Neighborhood | Transit, nearby amenities, practical notes, citations |
| Sources | Citations for neighborhood / transit / amenity claims |
| Booking | Date, slots, confirmation state, confirmation code |

Feel: conversational, trustworthy, transparent, fast, minimal, data-grounded.  
Avoid: generic chat UI, long paragraphs, fake claims, feature overload.  
Always answer: **Why should I consider this property?**

---

## Booking & n8n

**Booking:** voice slot negotiation → confirm → show code in UI.

**n8n:** receive shortlist → format → PDF → email. PDF includes preferences, listings, rent/BHK/amenities, match reasoning, neighborhood snapshot, citations, visit info if booked. Must be demoable.

---

## Failure handling

| Case | Response pattern |
| --- | --- |
| No matches | Offer to relax budget or location |
| Missing listing fields | Not enough verified info to evaluate |
| Missing neighborhood data | No reliable source found |
| No transit in OSM | “Couldn't find nearby transit in available OpenStreetMap data” (not absolute invention) |
| Listing unavailable | Drop from active shortlist |

---

## Architecture (recommended)

```text
Voice → STT → Intent → Preference extraction → Constraint manager
  → Property retrieval → OSM MCP → Neighborhood RAG
  → Ranking engine → Explanation generator → Shortlist
  → Voice + UI → Site visit booking → n8n → PDF → Email
```

| LLM owns | Deterministic / tools own |
| --- | --- |
| Understanding, extraction, clarification | Ranking / business rules (prefer deterministic) |
| NL explanations, voice replies | Listing facts, OSM POIs, RAG citations |

Do **not** rely on the LLM for factual neighborhood data.

---

## Non-negotiables (checklist)

- [ ] Voice-first path works end-to-end
- [ ] Real available listings only, with `source_url`
- [ ] Real OSM MCP call in demo
- [ ] RAG citations on every neighborhood claim
- [ ] Hard/soft constraints + stored include/exclude reasons
- [ ] Incremental voice refinement (no full reset)
- [ ] Session preference memory
- [ ] Site visit booking + UI confirmation
- [ ] n8n PDF email workflow
- [ ] Zero PII in storage/UI/logs/LLM context
- [ ] Never pretend to know unverifiable facts

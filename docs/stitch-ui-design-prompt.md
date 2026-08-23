# Property Scout — Google Stitch UI Design Prompts

Use at [stitch.withgoogle.com](https://stitch.withgoogle.com). Toggle **Web** (not App). Start in **Ideate** or **Gemini 3 Flash** for exploration; use **Thinking with 3.1 Pro** for final screens.

Optional: attach a screenshot of the current UI (`apps/web` companion page) via **Redesign** mode, then paste the master prompt below as refinement context.

---

## 1. Master prompt (paste first)

Design a **voice-first web companion UI** for **Property Scout** — an AI property discovery assistant for **Bengaluru renters**.

**Product principle:** Don’t just help users find listings. Help them understand whether a home fits their life. Never invent facts; show sources and citations.

**Platform:** Responsive web app (desktop primary, mobile usable). Max content width ~1200px. Accessible contrast, visible focus states, reduced-motion friendly.

**Vibe:** Calm, trustworthy, Bengaluru-native — warm paper background, deep forest ink, a single confident accent (teal or eucalyptus green). Feels like a premium rental concierge, not a generic PropTech dashboard. Avoid purple gradients, glassmorphism overload, and stock “AI chatbot” layouts.

**Layout (single main screen, scroll on mobile):**

**Header**
- Brand: “Property Scout”
- Subtitle: “Bengaluru · voice-first discovery”
- Status pill: API connected + session id (monospace, subtle)

**Left column — conversation (primary)**
1. **Voice hero panel** (most prominent)
   - Large circular mic button with recording state (idle / listening / processing)
   - Live transcript area while speaking
   - Helper example: “2BHK in Koramangala under ₹35,000, parking, near metro”
   - Toggle: “Speak replies” (TTS)
   - Friendly repeat prompt when speech is unclear (inline, not modal)

2. **Conversation thread**
   - User bubbles (right) vs Scout bubbles (left)
   - Optional small intent tag on user messages (`set_preferences`, `ask_why`, etc.)

3. **Text fallback**
   - Single-line input + Send
   - Secondary “Confirm search” button when phase = awaiting confirm

**Right column — structured truth panels**
4. **Your preferences** — live constraint summary:
   - Bedrooms, locality, max rent (₹), must-have amenities
   - Soft prefs: near metro, balcony, pet-friendly
   - Phase badge: `clarifying` | `awaiting confirm` | `shortlist` | `booking`

5. **Shortlist (3–5 cards)** — each card shows:
   - Society name, locality, rent/mo, BHK, sq ft, furnishing
   - Amenity chips (parking, balcony, etc.)
   - Match score (0–100) as a subtle badge
   - “Why shortlisted” one-liner + matched tags
   - Selected state with clear border

6. **Neighborhood snapshot** (for selected card)
   - Sections: Safety, Amenities, Transit (from cited notes)
   - OpenStreetMap nearby POIs list (metro, grocery, park) with distances
   - Small “OSM call id” for demo transparency

7. **Sources panel**
   - Citation cards: title (link), topic tag, snippet
   - Empty state: honest message that citations appear when grounded

**States to hint in design (use subtle UI, not separate screens):**
- Empty shortlist before search
- Clarifying (missing bedrooms / locality / budget)
- Shortlist populated after confirm
- Error banner for API offline (top, dismissible)

**Typography:** Distinctive pairing — characterful serif or humanist display for headings + clean sans for data/labels. Monospace for scores, session ids, citation ids.

**Do not include:** fake listing photos, invented neighborhood claims, login/signup, sidebar nav, dark hacker aesthetic, or a full map view (POI list is enough).

Generate **one high-fidelity desktop screen** in shortlist phase with sample data for Koramangala 2BHK listings, plus a **mobile breakpoint variant** below it.

---

## 2. DESIGN.md starter (import into Stitch)

```markdown
# Property Scout — Design System

## Brand
- Voice-first Bengaluru rental discovery
- Tone: calm, precise, citation-backed, never hype
- Principle: lifestyle fit over listing count

## Color (suggested — refine in Stitch)
- Background: #F4F0E8 (warm paper)
- Surface: #FFFFFF at 88% opacity
- Ink (text): #1C2A24
- Muted: #5C6B64
- Accent: #0F6B5C (eucalyptus teal)
- Accent soft: #D7EBE4
- User bubble: #E8F2EF
- Assistant bubble: #FFFDF9
- Error: #8A2F2F on #FDEEEE
- Success/connect: accent green dot

## Typography
- Display: distinctive serif or humanist (headings, society names)
- UI/body: clean sans (labels, chat, forms)
- Data: monospace (scores, session id, OSM call id, rent)

## Radius & elevation
- Cards: 0–4px radius (structured, not bubbly)
- Mic button: circular
- Shadows: minimal; prefer borders (#1C2A24 at 12% opacity)

## Components
- Phase badge: uppercase, small, pill
- Shortlist card: selectable, score top-right
- Citation row: linked title + topic chip + snippet
- Mic: primary CTA; red pulse when recording

## Motion
- Mic pulse when listening only
- Respect prefers-reduced-motion

## Content rules
- Rent in INR with ₹ and Indian grouping (₹32,000)
- Never show lat/long in UI
- Empty states use API-honest copy, no fabricated POIs
```

---

## 3. Screen flow (ask Stitch to “Stitch screens” after master)

Connect these screens in Play mode:

| # | Screen | Trigger |
|---|--------|---------|
| 1 | **Idle / welcome** | Session created, no prefs yet |
| 2 | **Clarifying** | Missing bedrooms or budget |
| 3 | **Awaiting confirm** | Prefs complete, Confirm CTA visible |
| 4 | **Shortlist** | 3–5 cards + neighborhood + sources |
| 5 | **Explain / why** | User asked “why the first one?” — highlight card + expanded reason |
| 6 | **Refine** | Toast or inline “Updated budget to ₹30,000” + refreshed cards |
| 7 | **Booking focus** | Phase = booking, visit slot placeholder (Phase 7) |

Prompt for flow:
> Using the same DESIGN.md, generate screens 2–4 as a connected prototype. Maintain identical header and preference panel; only conversation + shortlist content changes.

---

## 4. Follow-up refinement prompts (one change each)

**Voice emphasis**
> Make the microphone the primary hero in the left column — 2× larger, centered, with a soft radial glow when idle. Move text input below the fold on mobile.

**Shortlist cards**
> Redesign shortlist cards as horizontal scroll on mobile and stacked cards on desktop. Emphasize match score and “why shortlisted” with a left accent bar colored by score tier.

**Trust & citations**
> Add a persistent “Sources (3)” chip on the neighborhood panel header. Citation cards should look like footnotes, not ads — small, scannable, link-style titles.

**Preferences panel**
> Turn preferences into a compact “constraint chips” layout instead of a definition list. Unset fields show dashed “Add…” chips.

**Phase clarity**
> Add a thin progress stepper under the header: Preferences → Confirm → Shortlist → Book. Highlight current phase.

**Accessibility**
> Increase body text to 16px minimum, ensure 4.5:1 contrast on muted text, add visible focus rings on mic button and shortlist cards.

**Desktop density**
> Widen right column to 45% width; allow neighborhood + sources to share a tabbed panel (Neighborhood | Nearby POIs | Sources) to reduce scroll.

---

## 5. Sample content (use in mock data)

**User (voice):**
> I'm looking for a 2BHK in Koramangala under 35,000. I need parking and I want it close to a metro station.

**Scout:**
> Got it: 2BHK; Koramangala; under ₹35,000; must-have: parking; near metro. Say confirm if you want me to search available listings.

**Shortlist card 1:**
- Sony Signal Residency · Koramangala · 2 BHK · ₹32,000/mo · 1050 sq ft · semi-furnished
- Score: 88 · Matched: within budget, 2BHK, parking, location match
- Why: Strong match for all mandatory requirements.

**Neighborhood (cited):**
- Safety: Busy, well-lit mixed area; verify society security.
- Transit: Bus + metro catchments nearby.
- POI: metro Koramangala (~250m), grocery (~180m)

**Citation:**
- Koramangala — Wikipedia · topic: safety · snippet: “Residential-commercial neighbourhood in south-eastern Bengaluru…”

---

## 6. Export checklist

After design sign-off in Stitch:
- [ ] Export to Figma for component polish
- [ ] Export HTML/CSS or paste into Cursor for `apps/web/src/components/`
- [ ] Map Stitch components → existing React components:
  - VoiceControls, ConversationHistory, TurnInput
  - PreferenceSummary, ShortlistCards, NeighborhoodSnapshot, SourcesPanel
- [ ] Keep API field bindings unchanged (`SessionSnapshot`, `ShortlistItem`, `Citation`)

---

## 7. Live Mode voice brief (optional)

If using Stitch Live Mode, say:

> Interview me about Property Scout’s voice-first Bengaluru rental UI. I want a trustworthy companion layout with a prominent mic, live transcript, shortlist cards with match scores, and a citations panel. Avoid generic AI purple dashboards. Propose three layout directions, then refine the best one for desktop and mobile.

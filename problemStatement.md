# Voice-First AI Property Scout

## Overview

Build a **deployed voice-first AI property discovery assistant for Bengaluru** that helps renters and buyers find properties from spoken preferences, evaluates whether listings fit their lifestyle, explains shortlist decisions, supports voice-based refinement, and books site visits.

### Core product principle

> Don't just help users find properties. Help them understand whether a property actually fits their life.

### What the assistant combines

1. Real currently available property listings
2. Real neighborhood and geospatial data
3. Voice-based conversational interaction
4. RAG-grounded explanations with citations
5. Transparent shortlist reasoning
6. Voice-based shortlist refinement
7. Site-visit booking
8. n8n automation to generate and email a PDF shortlist

---

## 1. Primary user problem

People can easily find property listings, but struggle to judge whether a property is actually suitable for their lifestyle.

Typical unanswered questions:

- Is the commute realistic?
- Is the property within a reasonable distance of transit?
- Is the neighborhood suitable for their needs?
- Does the property have the required amenities?
- Is paying more for an additional bedroom worthwhile?
- Why was one property shortlisted while another was rejected?

The product must answer these using **real data**, not generic AI assumptions.

---

## 2. Core user experience

Primary interaction is **voice-first**.

### Example flow

**User:** "I'm looking for a 2BHK in Koramangala, budget 35k, need parking, close to a metro station."

**Assistant should:**

1. **Extract preferences**
   - Location = Koramangala
   - Bedrooms = 2
   - Budget = ₹35,000/month
   - Must-have = parking
   - Preference = near metro

2. Identify missing critical information
3. Ask clarification questions only when genuinely required (**max 5**)
4. Confirm final constraints before searching
5. Search the real listing dataset
6. Enrich each candidate with nearby transit, amenities, neighborhood info, and practical guidance
7. Rank listings against user preferences
8. Present a shortlist

---

## 3. Voice-based shortlist refinement

Users must be able to modify the shortlist conversationally, for example:

- "Drop anything above 40k."
- "Only show me places within 15 minutes of a metro station."
- "I need something pet-friendly."
- "Add one more option with a balcony."
- "Remove anything without parking."
- "Show me something cheaper."
- "Why did you remove that property?"

### Rules

- Only modify the **affected constraint**
- Do **not** regenerate the entire experience unnecessarily
- Maintain existing preferences and conversation context

**Example:** Initial `2BHK + Koramangala + ₹35K + parking` → user says "increase my budget to ₹40K" → update budget only; keep bedrooms, location, and parking.

---

## 4. Shortlist reasoning

Every listing needs a transparent reason for inclusion or exclusion.

The assistant must answer:

- Why did you pick this one?
- Why didn't you pick this property?
- Why is this better than the other option?
- Is the commute realistic?
- What's this neighborhood actually like?
- Does this area have metro access?
- Is this property within my budget?

### Grounding rules

- Reasoning must be based on **actual data**
- Do **not** say vague claims like "This is a great neighborhood"
- Prefer grounded statements, e.g. "OpenStreetMap shows X metro/transit points within the defined radius. The neighborhood guide describes the area as [...]."
- Every neighborhood claim must have a **citation**

---

## 5. Data sources

### Property listings

- Source: [https://bengaluru.rent/](https://bengaluru.rent/)
- Use only listings explicitly marked as **currently available**
- Exclude listings marked "Not for rent" or equivalent transparency-only status
- Retain a traceable `source_url` back to the original scraped listing

### Required listing fields

| Field | Description |
| --- | --- |
| `listing_id` | Unique identifier |
| `source_url` | Original listing URL |
| `location` | Location |
| `locality` | Locality / neighborhood |
| `rent` | Rent amount |
| `bedrooms` | Bedroom count |
| `furnishing` | Furnishing status |
| `amenities` | Amenities list |
| `society_name` | Society / building name |
| `square_footage` | Area |
| `availability_status` | Availability |
| `latitude` | Latitude |
| `longitude` | Longitude |

### PII removal (mandatory)

Remove **all PII** before data enters the database, application, UI, logs, or LLM context.

Never store or display:

- Owner names
- Agent names
- Phone numbers
- Personal contact information

---

## 6. OpenStreetMap MCP

The orchestration layer **must** integrate the [OpenStreetMap MCP](https://github.com/jagan-shanmugam/open-streetmap-mcp).

Use it for nearby:

- Metro stations and transit points
- Restaurants, schools, hospitals
- Grocery stores, parks, and other POIs

The system must **not invent** nearby places. The demo must show an **actual OpenStreetMap MCP call**.

```text
Listing coordinates
        ↓
OpenStreetMap MCP
        ↓
Nearby POIs
        ↓
Structured neighborhood context
        ↓
Shortlist ranking / explanation
```

---

## 7. RAG (neighborhood guidance)

Use RAG for neighborhood-level practical guidance:

- Neighborhood character
- Safety-related public information
- Lifestyle and transit context
- Amenities context
- Local area descriptions

### Sources

Prefer real public sources such as Wikipedia, city/neighborhood guides, and other trustworthy public sources.

Every retrieved source must retain:

- Title
- URL
- Source snippet / content reference
- Locality / topic

### Rules

- Every neighborhood claim shown to the user must have a citation
- Never use the LLM's general knowledge for unsupported neighborhood claims
- If reliable information cannot be found: *"I couldn't find reliable public information to verify this."*
- Do **not** guess

---

## 8. Shortlist ranking

Use a transparent ranking/scoring system.

### Suggested scoring dimensions

- Budget match
- Bedroom match
- Location match
- Must-have amenities
- Transit proximity
- Lifestyle preferences
- Availability

### Hard constraints vs soft preferences

| Type | Behavior | Example |
| --- | --- | --- |
| Hard constraints | Normally exclude on failure | 2BHK, Koramangala, ≤ ₹35K, Parking |
| Soft preferences | Affect ranking | Near metro, Balcony, Pet-friendly |

Store the reason for every inclusion/exclusion, e.g.:

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

## 9. Companion UI

Keep the UI **minimal and modern**.

### Required components

| Area | Contents |
| --- | --- |
| **A. Voice interaction** | Microphone button, recording state, live transcript, assistant response, conversation history |
| **B. Preference summary** | Location, budget, bedrooms, must-haves, preferences, commute point |
| **C. Shortlist cards** | Society name, locality, rent, bedrooms, area, key amenities, availability, match score, why shortlisted |
| **D. Neighborhood snapshot** | Transit, nearby amenities, practical notes, sources/citations |
| **E. Sources / references** | Citations for neighborhood, transit, and amenity claims |
| **F. Visit booking** | Preferred date, available time slots, confirmation state, confirmation code |

---

## 10. Site visit booking

Allow booking a site visit through voice once the user has a shortlist.

**Example:**

1. User: "I like the second one. Can I visit Saturday afternoon?"
2. Assistant: "Saturday afternoon has two available slots: 2 PM and 4 PM. Which would you prefer?"
3. User: "4 PM."
4. Assistant: "Your site visit is confirmed for Saturday at 4 PM. Your confirmation code is ABC123."

The booking must be reflected in the UI.

---

## 11. n8n workflow

Implement an n8n workflow that:

1. Receives the final shortlist
2. Formats listings and neighborhood information
3. Creates a PDF
4. Emails the PDF to the user

### PDF contents

- User preferences
- Shortlisted properties
- Rent, bedrooms, amenities
- Match reasoning
- Neighborhood snapshot
- Sources / citations
- Site visit information if booked

The workflow should be demonstrable.

---

## 12. Failure states

| Situation | Expected behavior |
| --- | --- |
| No matching listings | Suggest relaxing budget or location |
| Missing listing data | Say there isn't enough verified information |
| Missing neighborhood data | Say no reliable source was found |
| No nearby transit | Say none was found in OpenStreetMap data — do **not** invent "no metro nearby" as absolute fact |
| Unavailable listing | Remove from the active shortlist |

---

## 13. Conversation memory

Maintain preferences throughout the session.

- Do not ask the user to repeat previously provided information
- Incremental requests should merge with existing constraints

**Example:** "I want a 2BHK under 35K." later followed by "Show me something with a balcony." → interpret as `2BHK + under ₹35K + balcony`.

---

## 14. Privacy

Never expose PII. Before storing or passing scraped listing data to an LLM, remove:

- Names
- Phone numbers
- Email addresses
- Agent details
- Owner details

Avoid logging PII.

---

## 15. Design principles

### Feel

Conversational · Trustworthy · Transparent · Fast · Minimal · Data-grounded

### Avoid

- Generic AI chat UI
- Long paragraphs
- Fake neighborhood claims
- Unsupported recommendations
- Excessive screens / feature overload

### Core question the experience must always answer

> Why should I consider this property?

---

## 16. Recommended architecture

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

### LLM vs deterministic logic

| Use LLM for | Do **not** use LLM for |
| --- | --- |
| Conversational understanding | Factual neighborhood data |
| Preference extraction | Inventing POIs / amenities |
| Clarification | Unsupported recommendations |
| Natural language explanations | Ranking/business facts (prefer deterministic) |
| Voice responses | |

Keep ranking/business logic **deterministic where possible**.

---

## 17. Demo scenario

The final application should support this complete flow:

1. User clicks microphone
2. User says: *"I'm looking for a 2BHK in Koramangala under 35,000. I need parking and I want it close to a metro station."*
3. Assistant extracts preferences
4. Asks only necessary clarification questions
5. Confirms preferences
6. Retrieves currently available listings
7. Filters and ranks listings
8. Calls OpenStreetMap MCP for nearby POIs/transit
9. Retrieves neighborhood information through RAG
10. Produces **3–5** shortlisted listings
11. UI displays shortlist cards
12. User asks: *"Why did you pick the first one?"*
13. Assistant gives a grounded explanation with sources visible in UI
14. User says: *"Drop anything above 32K and show me something pet-friendly."*
15. Only the relevant shortlist constraints are updated
16. User selects a property
17. User says: *"I want to visit this Saturday at 4."*
18. Assistant confirms available slot
19. Booking confirmation is displayed
20. User clicks: *"Email me this shortlist."*
21. n8n generates a PDF
22. PDF is emailed to the user

---

## 18. Success criteria

The project succeeds if a user can complete the entire journey using voice:

```text
PREFERENCES → SEARCH → SHORTLIST → UNDERSTAND → REFINE → COMPARE → BOOK → RECEIVE PDF
```

And every factual recommendation is **traceable to real data**.

### Most important rule

The assistant should **never pretend to know something it cannot verify**.

If the data isn't available, say so clearly.

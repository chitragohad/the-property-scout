# Property Scout — AI Evaluations

Automated evaluation suites verify **correctness** of shortlist outputs, voice-edit state transitions, and grounding against authoritative datasets. These are not smoke tests — each case compares AI output to deterministic sources of truth.

## Quick start

From the repository root:

```bash
npm run evals
```

This runs all three suites via **pytest** (the project's existing backend test framework) and prints a summary report.

Equivalent:

```bash
cd apps/api && .venv/bin/python ../../evals/run_evals.py
```

## What each suite measures

### 1. Feasibility (`evals/test_feasibility_eval.py`)

| Check | Source of truth | Pass criteria |
|-------|-----------------|---------------|
| Budget compliance | Session `constraints.hard.max_rent` | Every shortlisted listing has `rent ≤ max_rent` |
| Must-have compliance | Hard constraints + listing amenities | Bedrooms, locality, and each must-have amenity match |
| Commute consistency | OSM POI distances on each listing pin | Near-transit claims align with metro POI data; no unsourced minute-level commute claims |

**Commute assumptions**

- Full route-based commute to `commute_point` is **not implemented** in the product yet.
- Evaluations compare **transit claims** (matched tags, neighborhood notes, rank reasons) against **OSM metro POI distances** for each listing.
- **Tolerance:** `800m` — matches the default OSM enrichment radius (`METRO_POI_NEAR_METRO_TOLERANCE_M` in `evals/lib/feasibility.py`).
- Specific minute counts (e.g. “12 minutes to Manyata”) **fail** unless backed by OSM metro distance data (currently not converted to minutes).

### 2. Edit Correctness (`evals/test_edit_correctness_eval.py`)

| Check | How it works |
|-------|--------------|
| Change budget / location / preferences | Snapshot session state before & after deterministic voice commands (`gemini=None`, heuristic NLU) |
| Regenerate shortlist | Refine triggers full re-search; verify new shortlist satisfies updated budget |
| Remove listing | Validates **reference remove edit** via `evals/lib/edit_state.py` (product voice-remove is not implemented yet) |
| Preserve unrelated state | Deep diff ensures only allowed paths changed |

**Allowed changes on refine:** `constraints.hard.max_rent`, `constraints.hard.locality`, `constraints.hard.must_have_amenities`, soft prefs, `shortlist_ids`, `phase`, `citation_count`.

**Failure:** Any change to unrelated fields (e.g. budget changing during a remove-listing reference test) fails the diff.

### 3. Grounding & Hallucination (`evals/test_grounding_eval.py`)

| Check | Source of truth | Pass criteria |
|-------|-----------------|---------------|
| Listing IDs grounded | `data/listings.normalized.json` | Every `listing_id` exists in authoritative inventory |
| Availability grounded | Same dataset (`availability_status`) | Shortlist cannot claim available when dataset says otherwise |
| Neighborhood citations | `data/rag/chunks.json` + listing guidance sources | Notes cite valid RAG IDs or approved IDs (`osm`, `listing-guidance`, `unverified`, …) |
| Missing neighborhood uncertainty | RAG unverified localities | When RAG misses, notes must include `UNVERIFIABLE` text |

## Negative / detector cases

Each suite includes **detector** cases that inject invalid data and assert the evaluator catches it. These prove the checks are not tautologies.

Examples:

- Over-budget listing injected → budget detector fires
- Fake listing ID → grounding detector fires
- Hallucinated neighborhood without uncertainty → grounding detector fires

## Source of truth files

| Asset | Path |
|-------|------|
| Authoritative listing IDs | `data/listings.normalized.json` |
| Full listing records (eval runtime) | Seeded SQLite DB (`ListingRow` via ingest) |
| RAG neighborhood index | `data/rag/chunks.json` |
| Runtime DB (seeded in eval fixtures) | SQLite via `workers/ingest/upsert.py` seed |
| OSM POIs (eval mode) | `OSM_MODE=static` deterministic POIs per listing pin |

## Determinism

Evaluations use:

- `OrchestratorDeps(gemini=None)` — heuristic intent & preference extraction only
- `OSM_MODE=static` — reproducible POI enrichment
- Fresh SQLite DB per test via pytest fixtures (`evals/conftest.py`)

## What constitutes a failure

- Any `@eval_case` assertion fails → marked ✗ in the report
- pytest exit code non-zero
- Feasibility: budget exceeded, must-have missing, transit claim inconsistent with OSM
- Edit: unintended field changes in session snapshot diff
- Grounding: unknown listing ID, false availability, invalid/missing citations, missing uncertainty on RAG miss

## Report format

Console output:

```
AI EVALUATION RESULTS

Feasibility
✓ Budget compliance
...

Overall: 12/12 PASS
```

### Downloadable reports

Each run also writes files under `evals/reports/`:

| File | Format |
|------|--------|
| `evals/reports/evals-report.json` | Machine-readable JSON (latest) |
| `evals/reports/evals-report.md` | Markdown summary (latest) |
| `evals/reports/evals-report-<timestamp>.{json,md}` | Timestamped archive copies |

Generate:

```bash
npm run evals
# or explicitly
npm run evals:report
```

Custom output directory:

```bash
cd apps/api && .venv/bin/python ../../evals/run_evals.py --output-dir /path/to/reports --format both
```

## Limitations

1. **Remove listing by voice** is not implemented in the orchestrator; edit eval validates reference remove logic and live refine/budget/locality paths.
2. **Commute routing** to `commute_point` is schema-only; feasibility checks internal transit consistency, not Google Maps travel times.
3. **Gemini-dependent** NLU paths are not covered — evals intentionally use deterministic heuristics for reproducibility.

## Layout

```
evals/
  README.md
  run_evals.py          # entrypoint for npm run evals
  conftest.py           # DB seed + orchestrator fixtures
  lib/
    dataset.py          # authoritative loaders
    feasibility.py      # budget / must-have / transit checks
    edit_state.py       # snapshot + deep diff helpers
    grounding.py        # listing + citation + uncertainty checks
    report.py           # summary printer
  test_feasibility_eval.py
  test_edit_correctness_eval.py
  test_grounding_eval.py
```

# Property Scout AI Evaluation Results

- **Generated:** 2026-08-23T06:12:43.216593+00:00
- **Overall:** 22/22 PASS

## Edit Correctness

_8/8 passed_

- [PASS] Change budget
- [PASS] Change location
- [PASS] Add preference
- [PASS] Regenerate shortlist
- [PASS] Remove listing
- [PASS] Preserve unrelated state
- [PASS] Detector: unintended budget change
- [PASS] Detector: remove listing by id

## Feasibility

_6/6 passed_

- [PASS] Budget compliance
- [PASS] Must-have compliance
- [PASS] Commute consistency
- [PASS] Detector: budget violation
- [PASS] Detector: must-have violation
- [PASS] Detector: unsupported commute minutes

## Grounding & Hallucination

_8/8 passed_

- [PASS] Listing IDs grounded
- [PASS] Availability grounded
- [PASS] Neighborhood citations
- [PASS] Missing neighborhood uncertainty
- [PASS] Detector: fake listing ID
- [PASS] Detector: unavailable listing claim
- [PASS] Detector: unsupported neighborhood citation
- [PASS] Detector: missing uncertainty language

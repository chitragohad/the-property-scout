"""Intent classification — Gemini when available, deterministic heuristics otherwise."""

from __future__ import annotations

import re
from typing import Literal

from app.schemas.session import SessionPhase
from app.services.gemini import GeminiClient

Intent = Literal[
    "set_preferences",
    "clarify_answer",
    "confirm_search",
    "refine_constraints",
    "remove_listing",
    "ask_why",
    "compare",
    "ask_neighborhood",
    "book_visit",
    "email_shortlist",
    "out_of_scope",
]

INTENTS: tuple[Intent, ...] = (
    "set_preferences",
    "clarify_answer",
    "confirm_search",
    "refine_constraints",
    "remove_listing",
    "ask_why",
    "compare",
    "ask_neighborhood",
    "book_visit",
    "email_shortlist",
    "out_of_scope",
)

_PREF_HINT = re.compile(
    r"(?i)("
    r"\b\d\s*bhk\b|"
    r"\bbedrooms?\b|"
    r"\bunder\s*\d[\d,]*|"
    r"\bbelow\s*\d[\d,]*|"
    r"\bbudget\b|"
    r"\brent\b|"
    r"\bkoramangala\b|"
    r"\bhsr\b|"
    r"\bindiranagar\b|"
    r"\bwhitefield\b|"
    r"\bjayanagar\b|"
    r"\bparking\b|"
    r"\bmetro\b|"
    r"\bbalcony\b|"
    r"\bpet\b"
    r")"
)
_REFINE_VERB = re.compile(
    r"\b(change|instead|actually|update|refine|make it|lower|raise|increase|decrease|"
    r"only|switch|move|set|adjust)\b",
    re.I,
)
_REMOVE_HINT = re.compile(
    r"\b(remove|drop|delete|exclude|take off|get rid of|without|don't (?:show|want)|"
    r"skip|pass on)\b",
    re.I,
)


def classify_intent_heuristic(
    text: str,
    *,
    phase: SessionPhase = "idle",
    missing_critical: list[str] | None = None,
) -> Intent:
    t = text.strip().lower()
    if not t:
        return "out_of_scope"

    if re.search(r"\b(email|send).*(shortlist|pdf|list)\b", t) or "email me" in t:
        return "email_shortlist"
    if phase == "booking" and re.search(
        r"\b(\d{1,2}(:\d{2})?\s*(am|pm)|morning|afternoon|evening|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        t,
    ):
        return "book_visit"
    if re.search(r"\b(book|visit|site visit|schedule|tour)\b", t):
        return "book_visit"
    if re.search(r"\b(compare|versus|vs\.?|better than|difference)\b", t):
        return "compare"
    if re.search(r"\b(why|how come|reason)\b", t):
        return "ask_why"
    if re.search(
        r"\b(neighborhood|neighbourhood|area like|safe|safety|amenities around|what's .* like)\b",
        t,
    ):
        return "ask_neighborhood"
    if re.search(r"\b(yes|confirm|looks good|go ahead|search now|that'?s right|proceed)\b", t):
        return "confirm_search"

    # While viewing a shortlist, preference edits and removals update the list immediately.
    if phase in {"shortlist", "booking"}:
        if _REMOVE_HINT.search(t):
            listing_target = re.search(
                r"\b(first|second|third|1st|2nd|3rd|listing|option|one|home|flat|#?\d)\b",
                t,
            )
            constraint_target = re.search(
                r"\b(parking|balcony|metro|pet|budget|rent|requirement|constraint|filter|amenity)\b",
                t,
            )
            if listing_target or not constraint_target:
                return "remove_listing"
            return "refine_constraints"
        if _REFINE_VERB.search(t) or _PREF_HINT.search(t):
            return "refine_constraints"

    if _REFINE_VERB.search(t) and (
        re.search(r"\b(budget|rent|bhk|bedroom|locality|parking|metro|balcony)\b", t)
        or phase == "shortlist"
    ):
        return "refine_constraints"
    if phase == "clarifying" and missing_critical:
        return "clarify_answer"
    if _PREF_HINT.search(t):
        return "set_preferences"
    return "out_of_scope"


def classify_intent(
    text: str,
    *,
    phase: SessionPhase = "idle",
    missing_critical: list[str] | None = None,
    client: GeminiClient | None = None,
) -> Intent:
    gemini = client
    if gemini is not None and gemini.available:
        try:
            system = (
                "You classify property-scout user turns. "
                f"Reply with ONLY one intent label from: {', '.join(INTENTS)}. "
                "Rules: "
                "If phase is shortlist or booking and the user changes budget/locality/BHK/"
                "amenities/preferences, use refine_constraints (not set_preferences). "
                "If they ask to remove/drop/exclude a shortlisted home, use remove_listing. "
                "No punctuation or explanation."
            )
            prompt = (
                f"phase={phase}\nmissing_critical={missing_critical or []}\n"
                f"user_text={text}\nintent:"
            )
            raw = gemini.generate_text(prompt, system=system).strip().lower()
            for intent in INTENTS:
                if intent in raw.replace(" ", "_") or intent == raw:
                    return intent  # type: ignore[return-value]
            token = re.sub(r"[^a-z_]", "", raw.replace(" ", "_"))
            if token in INTENTS:
                return token  # type: ignore[return-value]
        except Exception:
            pass
    return classify_intent_heuristic(text, phase=phase, missing_critical=missing_critical)

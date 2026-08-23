"""Conversation orchestrator — routes intents to deterministic pipelines."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.schemas.constraints import PreferencePatch
from app.schemas.session import (
    Booking,
    ConversationTurn,
    ShortlistItem,
    TurnResponse,
)
from app.services.explain import (
    compare_items,
    explain_why_not,
    explain_with_optional_gemini,
)
from app.services.booking import (
    BookingError,
    BookingSlotUnavailableError,
    afternoon_slots,
    available_slots,
    confirm_booking,
    confirmation_message,
    format_slot_display,
    offer_slots_message,
    parse_visit_request,
)
from app.services.export import export_shortlist_email, extract_email_from_text
from app.services.extract import extract_preferences
from app.services.gemini import GeminiClient
from app.services.intent import Intent, classify_intent
from app.services.rag import UNVERIFIABLE
from app.services.retrieval import find_candidates
from app.services.session_store import SessionRecord


@dataclass
class OrchestratorDeps:
    db: Session
    gemini: GeminiClient | None = None


def _assistant(record: SessionRecord, text: str, intent: Intent | None = None) -> TurnResponse:
    record.turns.append(ConversationTurn(role="assistant", text=text, intent=intent))
    # Always include shortlist (including []) so the UI can clear/replace cards after refine.
    return TurnResponse(
        assistant_text=text,
        constraints=record.constraints.constraints,
        shortlist=list(record.shortlist),
        citations=list(record.citations),
        booking=record.booking,
        phase=record.phase,
    )


def _patch_has_updates(patch: PreferencePatch) -> bool:
    if patch.commute_point:
        return True
    if patch.hard is not None:
        hard = patch.hard.model_dump(exclude_unset=True)
        if hard.get("bedrooms") is not None or hard.get("locality") or hard.get("max_rent") is not None:
            return True
        if hard.get("must_have_amenities"):
            return True
    if patch.soft is not None:
        soft = patch.soft.model_dump(exclude_unset=True)
        if any(v is not None for v in soft.values()):
            return True
    return False


def _summarize_constraints(record: SessionRecord) -> str:
    c = record.constraints.constraints
    hard = c.hard
    soft = c.soft
    bits = []
    if hard.bedrooms is not None:
        bits.append(f"{hard.bedrooms}BHK")
    if hard.locality:
        bits.append(hard.locality)
    if hard.max_rent is not None:
        bits.append(f"under ₹{hard.max_rent}")
    if hard.must_have_amenities:
        bits.append("must-have: " + ", ".join(hard.must_have_amenities))
    if soft.near_metro:
        bits.append("near metro")
    if soft.balcony:
        bits.append("balcony")
    if soft.pet_friendly:
        bits.append("pet-friendly")
    return "; ".join(bits) if bits else "no preferences set yet"


def _clarify_question(missing: list[str]) -> str:
    labels = {
        "bedrooms": "how many bedrooms (BHK)",
        "locality": "which locality",
        "max_rent": "your maximum rent budget",
    }
    readable = [labels.get(m, m) for m in missing]
    if len(readable) == 1:
        return f"To search, I still need {readable[0]}. What should I use?"
    return "To search, I still need: " + ", ".join(readable) + ". What's your preference?"


def _run_search(record: SessionRecord, deps: OrchestratorDeps) -> str:
    constraints = record.constraints.constraints
    candidates = find_candidates(deps.db, constraints.hard, limit=50)
    if not candidates:
        record.shortlist = []
        record.citations = []
        record.excluded = []
        record.phase = "awaiting_confirm"
        return (
            "I couldn't find available listings matching those hard filters. "
            "Try relaxing max rent or locality."
        )

    enriched = record.enrichment.build_enriched_shortlist(
        candidates,
        constraints,
        max_size=5,
    )
    record.shortlist = enriched.shortlist
    record.excluded = list(enriched.excluded)
    record.citations = list(enriched.citations)
    record.phase = "shortlist"
    record.awaiting_explicit_confirm = False

    if not record.shortlist:
        record.phase = "awaiting_confirm"
        return (
            "No listings passed ranking for the shortlist. "
            "Consider relaxing budget or must-have amenities."
        )

    count = len(record.shortlist)
    summary = _summarize_constraints(record)
    return (
        f"I found {count} option{'s' if count != 1 else ''} for {summary}. "
        "I've updated the Shortlist tab with the latest matches. "
        "You can ask why I picked one, compare two, refine again, or remove a listing."
    )


def _apply_patch(record: SessionRecord, text: str, deps: OrchestratorDeps) -> PreferencePatch:
    patch = extract_preferences(text, client=deps.gemini)
    record.constraints.merge(patch)
    return patch


def _remove_shortlist_item(record: SessionRecord, text: str) -> str:
    if not record.shortlist:
        return "There is no shortlist to edit yet."

    item = _select_focus_item(record, text)
    if item is None:
        return "I couldn't tell which listing to remove. Try saying 'remove the first one'."

    listing_id = item.listing.listing_id
    name = item.listing.society_name
    record.shortlist = [s for s in record.shortlist if s.listing.listing_id != listing_id]
    if record.selected_listing_id == listing_id:
        record.selected_listing_id = (
            record.shortlist[0].listing.listing_id if record.shortlist else None
        )
    if record.booking and record.booking.listing_id == listing_id:
        record.booking = None
        if record.phase == "booking":
            record.phase = "shortlist"

    remaining = len(record.shortlist)
    if remaining == 0:
        return (
            f"Removed {name}. Your shortlist is empty — refine preferences or confirm a new search."
        )
    return (
        f"Removed {name}. Showing {remaining} remaining option"
        f"{'s' if remaining != 1 else ''}."
    )


def _select_focus_item(record: SessionRecord, text: str) -> ShortlistItem | None:
    if not record.shortlist:
        return None
    t = text.lower()
    m = re.search(r"\b(?:first|1st|#?1)\b", t)
    if m:
        return record.shortlist[0]
    m = re.search(r"\b(?:second|2nd|#?2)\b", t)
    if m and len(record.shortlist) > 1:
        return record.shortlist[1]
    m = re.search(r"\b(?:third|3rd|#?3)\b", t)
    if m and len(record.shortlist) > 2:
        return record.shortlist[2]
    if record.selected_listing_id:
        for item in record.shortlist:
            if item.listing.listing_id == record.selected_listing_id:
                return item
    # Match society name fragment
    for item in record.shortlist:
        if item.listing.society_name.lower() in t or item.listing.listing_id.lower() in t:
            return item
    return record.shortlist[0]


def _booking_listing_name(record: SessionRecord, listing_id: str) -> str:
    for item in record.shortlist:
        if item.listing.listing_id == listing_id:
            return item.listing.society_name
    return "your selected home"


def _negotiate_booking(record: SessionRecord, text: str, *, intent: Intent) -> TurnResponse | None:
    if not record.shortlist or record.booking is None:
        return None
    if record.booking.status == "confirmed":
        parsed = parse_visit_request(text)
        if parsed.target_date or parsed.slot or parsed.period:
            record.booking.status = "pending"
            record.booking.confirmation_code = None
        else:
            return _assistant(
                record,
                f"You already have visit {record.booking.confirmation_code} booked. "
                "Say a new day and time if you want to reschedule.",
                intent,
            )

    listing_id = record.booking.listing_id or record.selected_listing_id
    if not listing_id:
        return None

    parsed = parse_visit_request(text)
    pending = record.booking

    target_date = parsed.target_date
    if target_date is None and pending.date:
        target_date = date.fromisoformat(pending.date)

    slot = parsed.slot or (pending.slot if pending.slot else None)

    if target_date is None and slot is None and parsed.period is None:
        return None

    if target_date is None:
        return _assistant(
            record,
            "Which day would you like to visit? For example, Saturday or Sunday.",
            intent,
        )

    if parsed.period and slot is None:
        slots = afternoon_slots(target_date) if parsed.period == "afternoon" else available_slots(target_date)
        if not slots:
            return _assistant(
                record,
                f"I don't have open slots on {target_date.strftime('%A')}. Try another day.",
                intent,
            )
        pending.date = target_date.isoformat()
        pending.listing_id = listing_id
        record.booking = pending
        return _assistant(record, offer_slots_message(target_date, slots), intent)

    if slot is None:
        slots = available_slots(target_date)
        if not slots:
            return _assistant(
                record,
                f"I don't have open slots on {target_date.strftime('%A')}. Try another day.",
                intent,
            )
        pending.date = target_date.isoformat()
        pending.listing_id = listing_id
        record.booking = pending
        return _assistant(record, offer_slots_message(target_date, slots), intent)

    try:
        booking = confirm_booking(record, listing_id, target_date, slot)
    except BookingSlotUnavailableError as exc:
        if not exc.alternatives:
            return _assistant(
                record,
                f"No slots are open on {target_date.strftime('%A')}. Try another day.",
                intent,
            )
        pending.date = target_date.isoformat()
        pending.listing_id = listing_id
        record.booking = pending
        alts = ", ".join(format_slot_display(s) for s in exc.alternatives)
        return _assistant(
            record,
            f"{format_slot_display(slot)} isn't available. Open slots that day: {alts}. "
            "Which would you prefer?",
            intent,
        )
    except BookingError as exc:
        return _assistant(record, str(exc), intent)

    society = _booking_listing_name(record, listing_id)
    return _assistant(record, confirmation_message(booking, society), intent)


def handle_turn(record: SessionRecord, text: str, deps: OrchestratorDeps) -> TurnResponse:
    record.turns.append(ConversationTurn(role="user", text=text, intent=None))
    missing = record.constraints.missing_critical()
    intent = classify_intent(
        text,
        phase=record.phase,
        missing_critical=missing,
        client=deps.gemini,
    )
    # Preference-like edits while viewing results must re-search even if Gemini
    # mislabels them as set_preferences.
    if (
        record.phase in {"shortlist", "booking"}
        and intent == "set_preferences"
        and record.shortlist
    ):
        intent = "refine_constraints"
    record.turns[-1].intent = intent

    if record.phase == "booking" and record.booking and record.booking.status != "confirmed":
        negotiated = _negotiate_booking(record, text, intent=intent)
        if negotiated is not None:
            return negotiated

    if intent == "out_of_scope":
        return _assistant(
            record,
            "I can help with Bengaluru rental preferences, shortlists, neighborhood questions "
            "with citations, refinements, and site-visit booking. What would you like to do?",
            intent,
        )

    if intent == "remove_listing":
        if not record.shortlist:
            return _assistant(
                record,
                "There is no shortlist yet. Confirm a search first, then ask me to remove a listing.",
                intent,
            )
        msg = _remove_shortlist_item(record, text)
        record.phase = "shortlist"
        return _assistant(record, msg, intent)

    if intent in {"set_preferences", "clarify_answer", "refine_constraints"}:
        patch = _apply_patch(record, text, deps)
        missing = record.constraints.missing_critical()
        viewing_results = record.phase in {"shortlist", "booking"} and (
            bool(record.shortlist) or intent == "refine_constraints"
        )

        if viewing_results and (intent == "refine_constraints" or _patch_has_updates(patch)):
            if record.booking and record.booking.status != "confirmed":
                record.booking = None
            msg = _run_search(record, deps)
            return _assistant(
                record,
                f"Updated preferences to {_summarize_constraints(record)}. {msg}",
                "refine_constraints",
            )

        if missing:
            if record.constraints.can_ask_clarification():
                record.constraints.record_clarification()
                record.phase = "clarifying"
                return _assistant(record, _clarify_question(missing), intent)
            record.phase = "awaiting_confirm"
            record.awaiting_explicit_confirm = True
            return _assistant(
                record,
                "I've hit the clarification limit. Here's what I have: "
                f"{_summarize_constraints(record)}. Say confirm to search anyway with gaps, "
                "or update a preference.",
                intent,
            )

        record.phase = "awaiting_confirm"
        record.awaiting_explicit_confirm = True
        return _assistant(
            record,
            f"Got it: {_summarize_constraints(record)}. "
            "Say confirm if you want me to search available listings.",
            intent,
        )

    if intent == "confirm_search":
        if record.constraints.missing_critical() and not record.awaiting_explicit_confirm:
            missing = record.constraints.missing_critical()
            if record.constraints.can_ask_clarification():
                record.constraints.record_clarification()
                record.phase = "clarifying"
                return _assistant(record, _clarify_question(missing), intent)
        msg = _run_search(record, deps)
        return _assistant(record, msg, intent)

    if intent == "ask_why":
        if not record.shortlist:
            return _assistant(record, "There is no shortlist yet. Confirm a search first.", intent)
        item = _select_focus_item(record, text)
        assert item is not None
        # why not?
        if re.search(r"\bwhy (?:not|didn't|did not)\b", text.lower()):
            if record.excluded:
                return _assistant(record, explain_why_not(record.excluded[0]), intent)
        text_out = explain_with_optional_gemini(item, question=text, client=deps.gemini)
        return _assistant(record, text_out, intent)

    if intent == "compare":
        if len(record.shortlist) < 2:
            return _assistant(record, "I need at least two shortlisted homes to compare.", intent)
        return _assistant(
            record,
            compare_items(record.shortlist[0], record.shortlist[1]),
            intent,
        )

    if intent == "ask_neighborhood":
        if not record.shortlist:
            return _assistant(
                record,
                "Confirm a search first so I can ground neighborhood notes to a locality.",
                intent,
            )
        item = _select_focus_item(record, text)
        assert item is not None
        text_out = explain_with_optional_gemini(
            item, question="neighborhood", client=deps.gemini
        )
        if not item.citations and (
            not item.neighborhood_notes
            or all(n.citation_id == "unverified" for n in item.neighborhood_notes)
        ):
            text_out = UNVERIFIABLE
        return _assistant(record, text_out, intent)

    if intent == "book_visit":
        if not record.shortlist:
            return _assistant(record, "Pick a shortlist first, then we can book a visit.", intent)
        item = _select_focus_item(record, text)
        assert item is not None
        record.selected_listing_id = item.listing.listing_id
        record.phase = "booking"
        record.booking = Booking(
            listing_id=item.listing.listing_id,
            date="",
            slot="",
            status="pending",
            confirmation_code=None,
        )

        parsed = parse_visit_request(text)
        if parsed.target_date or parsed.slot or parsed.period:
            negotiated = _negotiate_booking(record, text, intent=intent)
            if negotiated is not None:
                return negotiated

        return _assistant(
            record,
            f"Okay — focusing on {item.listing.society_name} for a site visit. "
            "Tell me a preferred day and time, for example Saturday at 4 PM.",
            intent,
        )

    if intent == "email_shortlist":
        if not record.shortlist:
            return _assistant(record, "No shortlist to email yet.", intent)
        spoken_email = extract_email_from_text(text)
        if spoken_email:
            result = export_shortlist_email(record, spoken_email)
            return _assistant(record, result.message, intent)
        return _assistant(
            record,
            f"I can email your {len(record.shortlist)} shortlisted homes. "
            "Enter your email on the Shortlist tab and tap Email me.",
            intent,
        )

    return _assistant(record, "I'm not sure how to help with that yet.", intent)


def confirm_search(record: SessionRecord, deps: OrchestratorDeps) -> TurnResponse:
    record.turns.append(
        ConversationTurn(role="user", text="[confirm-search]", intent="confirm_search")
    )
    msg = _run_search(record, deps)
    return _assistant(record, msg, "confirm_search")

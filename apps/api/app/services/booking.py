"""Site-visit booking — slot catalog, parsing, and confirmation codes."""

from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.schemas.session import Booking
from app.services.session_store import SessionRecord

IST = ZoneInfo("Asia/Kolkata")

WEEKDAY_SLOTS: tuple[str, ...] = ("11:00", "14:00", "16:00")
WEEKEND_SLOTS: tuple[str, ...] = ("10:00", "11:00", "14:00", "16:00", "18:00")

_DAY_NAMES = {
    "monday": 0,
    "monday's": 0,
    "tuesday": 1,
    "tuesday's": 1,
    "wednesday": 2,
    "wednesday's": 2,
    "thursday": 3,
    "thursday's": 3,
    "friday": 4,
    "friday's": 4,
    "saturday": 5,
    "saturday's": 5,
    "sunday": 6,
    "sunday's": 6,
}

Period = Literal["morning", "afternoon", "evening"] | None


class BookingError(Exception):
    """Base booking validation error."""


class BookingSlotUnavailableError(BookingError):
    """Requested slot is not in the catalog for that date."""

    def __init__(self, target_date: date, slot: str, alternatives: list[str]) -> None:
        self.target_date = target_date
        self.slot = slot
        self.alternatives = alternatives
        super().__init__(
            f"Slot {format_slot_display(slot)} is unavailable on "
            f"{format_date_display(target_date)}."
        )


@dataclass(frozen=True)
class ParsedVisit:
    target_date: date | None = None
    slot: str | None = None
    period: Period = None


def today_ist(reference: datetime | None = None) -> date:
    moment = reference or datetime.now(tz=IST)
    return moment.date()


def available_slots(target_date: date, *, reference: date | None = None) -> list[str]:
    """Return HH:MM slots available for site visits on ``target_date`` (IST demo catalog)."""
    ref = reference or today_ist()
    if target_date < ref:
        return []
    catalog = list(WEEKEND_SLOTS if target_date.weekday() >= 5 else WEEKDAY_SLOTS)
    return catalog


def afternoon_slots(target_date: date, *, reference: date | None = None) -> list[str]:
    return [slot for slot in available_slots(target_date, reference=reference) if slot >= "12:00"]


def format_slot_display(slot: str) -> str:
    hour, minute = (int(part) for part in slot.split(":"))
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    if minute:
        return f"{display_hour}:{minute:02d} {suffix}"
    return f"{display_hour} {suffix}"


def format_date_display(target_date: date) -> str:
    return target_date.strftime("%A, %d %b %Y")


def normalize_slot(raw: str) -> str:
    cleaned = raw.strip().lower().replace(".", "")
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", cleaned)
    if not match:
        raise BookingError(f"Could not parse time slot: {raw!r}")
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if meridiem is None and 1 <= hour <= 7:
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def generate_confirmation_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _resolve_day_name(token: str, reference: date) -> date:
    weekday = _DAY_NAMES.get(token.lower().rstrip("'s"))
    if weekday is None:
        raise BookingError(f"Unknown weekday: {token!r}")
    days_ahead = (weekday - reference.weekday()) % 7
    return reference + timedelta(days=days_ahead)


def parse_visit_request(text: str, *, reference: date | None = None) -> ParsedVisit:
    """Parse natural-language visit requests such as ``visit Saturday at 4``."""
    ref = reference or today_ist()
    lowered = text.strip().lower()
    target_date: date | None = None
    slot: str | None = None
    period: Period = None

    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", lowered)
    if iso_match:
        target_date = date.fromisoformat(iso_match.group(1))

    for token in _DAY_NAMES:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            target_date = _resolve_day_name(token, ref)
            break

    if re.search(r"\bthis afternoon\b|\bafternoon\b", lowered):
        period = "afternoon"
    elif re.search(r"\bmorning\b", lowered):
        period = "morning"
    elif re.search(r"\bevening\b", lowered):
        period = "evening"

    time_patterns = (
        r"\b(\d{1,2}:\d{2})\b",
        r"\b(\d{1,2})\s*(am|pm)\b",
        r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
    )
    for pattern in time_patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        groups = [g for g in match.groups() if g is not None]
        if not groups:
            continue
        if ":" in groups[0]:
            slot = normalize_slot(groups[0])
        else:
            hour = groups[0]
            minute = next((g for g in groups[1:] if g and g.isdigit()), "00")
            meridiem = next((g for g in groups[1:] if g in {"am", "pm"}), None)
            slot = normalize_slot(f"{hour}:{minute} {meridiem or ''}".strip())
        break

    if slot is None and re.search(r"\b4\s*pm\b|\bfour pm\b", lowered):
        slot = "16:00"
    if slot is None and re.search(r"\b2\s*pm\b|\btwo pm\b", lowered):
        slot = "14:00"

    return ParsedVisit(target_date=target_date, slot=slot, period=period)


def confirm_booking(
    record: SessionRecord,
    listing_id: str,
    target_date: date,
    slot: str,
    *,
    reference: date | None = None,
) -> Booking:
    """Validate slot, generate confirmation code, and persist booking on session."""
    ids = {item.listing.listing_id for item in record.shortlist}
    if ids and listing_id not in ids:
        raise BookingError("Listing is not in the current shortlist.")

    normalized = normalize_slot(slot)
    catalog = available_slots(target_date, reference=reference)
    if normalized not in catalog:
        raise BookingSlotUnavailableError(target_date, normalized, catalog)

    booking = Booking(
        listing_id=listing_id,
        date=target_date.isoformat(),
        slot=normalized,
        status="confirmed",
        confirmation_code=generate_confirmation_code(),
    )
    record.booking = booking
    record.selected_listing_id = listing_id
    record.phase = "booking"
    return booking


def offer_slots_message(target_date: date, slots: list[str]) -> str:
    rendered = ", ".join(format_slot_display(s) for s in slots)
    return (
        f"{format_date_display(target_date)} has these available slots: {rendered}. "
        "Which time works for you?"
    )


def confirmation_message(booking: Booking, society_name: str) -> str:
    visit_date = date.fromisoformat(booking.date)
    return (
        f"Your site visit to {society_name} is confirmed for "
        f"{format_date_display(visit_date)} at {format_slot_display(booking.slot)}. "
        f"Your confirmation code is {booking.confirmation_code}."
    )

"""Site visit booking tests."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.booking import (
    BookingSlotUnavailableError,
    afternoon_slots,
    available_slots,
    confirm_booking,
    confirmation_message,
    normalize_slot,
    parse_visit_request,
)
from app.services.orchestrator import OrchestratorDeps, handle_turn
from app.services.session_store import SessionRecord
from tests.test_explain import _item


@pytest.fixture()
def booking_record() -> SessionRecord:
    record = SessionRecord(session_id="sess-booking")
    record.shortlist = [_item()]
    record.selected_listing_id = record.shortlist[0].listing.listing_id
    return record


def test_available_slots_weekend_vs_weekday():
    saturday = date(2026, 8, 22)
    monday = date(2026, 8, 24)
    assert "16:00" in available_slots(saturday, reference=saturday)
    assert "10:00" in available_slots(saturday, reference=saturday)
    assert "10:00" not in available_slots(monday, reference=monday)


def test_afternoon_slots():
    saturday = date(2026, 8, 22)
    slots = afternoon_slots(saturday, reference=saturday)
    assert slots == ["14:00", "16:00", "18:00"]


def test_normalize_slot():
    assert normalize_slot("4 pm") == "16:00"
    assert normalize_slot("16:00") == "16:00"
    assert normalize_slot("2 PM") == "14:00"


def test_parse_visit_request_saturday_at_four():
    ref = date(2026, 8, 22)  # Saturday
    parsed = parse_visit_request("I want to visit this Saturday at 4", reference=ref)
    assert parsed.target_date == ref
    assert parsed.slot == "16:00"


def test_parse_visit_request_saturday_afternoon():
    ref = date(2026, 8, 20)  # Thursday
    parsed = parse_visit_request("Can I visit Saturday afternoon?", reference=ref)
    assert parsed.target_date == date(2026, 8, 22)
    assert parsed.slot is None
    assert parsed.period == "afternoon"


def test_confirm_booking_generates_code(booking_record: SessionRecord):
    visit_date = date(2026, 8, 22)
    listing_id = booking_record.shortlist[0].listing.listing_id
    booking = confirm_booking(booking_record, listing_id, visit_date, "16:00", reference=visit_date)
    assert booking.status == "confirmed"
    assert booking.confirmation_code
    assert len(booking.confirmation_code) == 6
    assert booking_record.booking == booking


def test_confirm_booking_rejects_unavailable_slot(booking_record: SessionRecord):
    visit_date = date(2026, 8, 24)  # Monday
    listing_id = booking_record.shortlist[0].listing.listing_id
    with pytest.raises(BookingSlotUnavailableError) as exc:
        confirm_booking(booking_record, listing_id, visit_date, "10:00", reference=visit_date)
    assert exc.value.alternatives


def test_confirmation_message():
    from app.schemas.session import Booking

    booking = Booking(
        listing_id="lst-1",
        date="2026-08-22",
        slot="16:00",
        status="confirmed",
        confirmation_code="ABC123",
    )
    text = confirmation_message(booking, "Green View Apartments")
    assert "ABC123" in text
    assert "4 PM" in text


def test_voice_book_saturday_at_four_flow(booking_record: SessionRecord, monkeypatch: pytest.MonkeyPatch):
    booking_record.phase = "shortlist"
    deps = OrchestratorDeps(db=None)  # type: ignore[arg-type]

    first = handle_turn(booking_record, "I'd like to book a visit", deps)
    assert first.phase == "booking"
    assert booking_record.booking is not None
    assert booking_record.booking.status == "pending"

    second = handle_turn(booking_record, "visit Saturday at 4", deps)
    assert booking_record.booking.status == "confirmed"
    assert booking_record.booking.confirmation_code
    assert "confirmation code" in second.assistant_text.lower()


def test_voice_saturday_afternoon_then_pick_slot(booking_record: SessionRecord):
    booking_record.phase = "shortlist"
    deps = OrchestratorDeps(db=None)  # type: ignore[arg-type]

    handle_turn(booking_record, "book a visit for the first one", deps)
    offer = handle_turn(booking_record, "Saturday afternoon", deps)
    assert "available slots" in offer.assistant_text.lower()

    confirm = handle_turn(booking_record, "4 PM", deps)
    assert booking_record.booking is not None
    assert booking_record.booking.status == "confirmed"
    assert booking_record.booking.slot == "16:00"
    assert booking_record.booking.confirmation_code in confirm.assistant_text

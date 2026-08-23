"""Session HTTP API — create/get/turn/confirm/select/book/export."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.session import Booking, ConversationTurn, SessionSnapshot, TurnRequest, TurnResponse
from app.services.booking import BookingError, BookingSlotUnavailableError, available_slots, confirm_booking
from app.services.export import export_shortlist_email
from app.services.gemini import GeminiClient
from app.services.orchestrator import OrchestratorDeps, confirm_search, handle_turn
from app.services.session_store import SessionStoreProtocol, get_session_store

router = APIRouter(prefix="/session", tags=["session"])


class SelectListingRequest(BaseModel):
    listing_id: str


class BookingRequest(BaseModel):
    listing_id: str
    date: str
    slot: str


class BookingSlotsResponse(BaseModel):
    date: str
    slots: list[str]


class ExportRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ExportResponse(BaseModel):
    ok: bool
    message: str
    delivered: bool = False
    payload: dict | None = None


def _store() -> SessionStoreProtocol:
    return get_session_store()


@router.post("", response_model=SessionSnapshot)
def create_session(store: SessionStoreProtocol = Depends(_store)) -> SessionSnapshot:
    record = store.create()
    store.save(record)
    return record.snapshot()


@router.get("/{session_id}", response_model=SessionSnapshot, response_model_exclude_none=True)
def get_session(session_id: str, store: SessionStoreProtocol = Depends(_store)) -> SessionSnapshot:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return record.snapshot()


@router.post(
    "/{session_id}/turn",
    response_model=TurnResponse,
    response_model_exclude_none=True,
)
def post_turn(
    session_id: str,
    body: TurnRequest,
    db: Session = Depends(get_db),
    store: SessionStoreProtocol = Depends(_store),
) -> TurnResponse:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    deps = OrchestratorDeps(db=db, gemini=GeminiClient())
    response = handle_turn(record, body.text, deps)
    store.save(record)
    return response


@router.post(
    "/{session_id}/confirm-search",
    response_model=TurnResponse,
    response_model_exclude_none=True,
)
def post_confirm_search(
    session_id: str,
    db: Session = Depends(get_db),
    store: SessionStoreProtocol = Depends(_store),
) -> TurnResponse:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    deps = OrchestratorDeps(db=db, gemini=GeminiClient())
    response = confirm_search(record, deps)
    store.save(record)
    return response


@router.post("/{session_id}/select-listing", response_model=SessionSnapshot, response_model_exclude_none=True)
def select_listing(
    session_id: str,
    body: SelectListingRequest,
    store: SessionStoreProtocol = Depends(_store),
) -> SessionSnapshot:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    ids = {item.listing.listing_id for item in record.shortlist}
    if body.listing_id not in ids:
        raise HTTPException(status_code=400, detail="listing_id not in shortlist")
    record.selected_listing_id = body.listing_id
    store.save(record)
    return record.snapshot()


@router.get("/{session_id}/booking/slots", response_model=BookingSlotsResponse)
def get_booking_slots(
    session_id: str,
    visit_date: str = Query(..., alias="date", description="ISO date YYYY-MM-DD"),
    store: SessionStoreProtocol = Depends(_store),
) -> BookingSlotsResponse:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        target_date = date.fromisoformat(visit_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format") from exc
    return BookingSlotsResponse(date=target_date.isoformat(), slots=available_slots(target_date))


@router.post("/{session_id}/bookings", response_model=Booking)
def create_booking(
    session_id: str,
    body: BookingRequest,
    store: SessionStoreProtocol = Depends(_store),
) -> Booking:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        target_date = date.fromisoformat(body.date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format") from exc

    try:
        booking = confirm_booking(record, body.listing_id, target_date, body.slot)
    except BookingSlotUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "alternatives": exc.alternatives,
            },
        ) from exc
    except BookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.save(record)
    return booking


@router.post("/{session_id}/export", response_model=ExportResponse)
def export_shortlist(
    session_id: str,
    body: ExportRequest,
    store: SessionStoreProtocol = Depends(_store),
) -> ExportResponse:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = export_shortlist_email(record, body.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record.turns.append(
        ConversationTurn(role="user", text="[email-shortlist]", intent="email_shortlist")
    )
    record.turns.append(
        ConversationTurn(role="assistant", text=result.message, intent="email_shortlist")
    )
    store.save(record)

    return ExportResponse(
        ok=result.ok,
        message=result.message,
        delivered=result.delivered,
        payload=result.payload if not result.delivered else None,
    )

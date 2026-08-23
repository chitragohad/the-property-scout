from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.constraints import Constraints
from app.schemas.listing import Listing
from app.schemas.osm import NeighborhoodNote, OsmContext
from app.schemas.ranking import Citation, RankResult

SessionPhase = Literal[
    "clarifying",
    "awaiting_confirm",
    "shortlist",
    "booking",
    "idle",
]


class ShortlistItem(BaseModel):
    listing: Listing
    rank: RankResult
    citations: list[Citation] = Field(default_factory=list)
    osm: OsmContext | None = None
    neighborhood_notes: list[NeighborhoodNote] = Field(default_factory=list)


class Booking(BaseModel):
    listing_id: str
    date: str
    slot: str
    status: Literal["pending", "confirmed", "cancelled"] = "pending"
    confirmation_code: str | None = None


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    intent: str | None = None


class SessionSnapshot(BaseModel):
    session_id: str
    phase: SessionPhase = "idle"
    clarification_count: int = 0
    constraints: Constraints = Field(default_factory=Constraints)
    shortlist: list[ShortlistItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    booking: Booking | None = None
    turns: list[ConversationTurn] = Field(default_factory=list)
    selected_listing_id: str | None = None


class TurnRequest(BaseModel):
    text: str


class TurnResponse(BaseModel):
    assistant_text: str
    constraints: Constraints
    shortlist: list[ShortlistItem] | None = None
    citations: list[Citation] | None = None
    booking: Booking | None = None
    phase: SessionPhase
    tts_audio_base64: str | None = None

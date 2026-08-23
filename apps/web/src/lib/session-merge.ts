import type { SessionSnapshot, TurnResponse } from "@property-scout/schemas";

/** Apply a turn response immediately so UI updates without waiting for GET /session. */
export function applyTurnResponse(
  snapshot: SessionSnapshot,
  userText: string,
  turn: TurnResponse,
): SessionSnapshot {
  const nextShortlist =
    turn.shortlist != null ? turn.shortlist : snapshot.shortlist;
  const keepSelected =
    snapshot.selected_listing_id &&
    nextShortlist.some((i) => i.listing.listing_id === snapshot.selected_listing_id);

  return {
    ...snapshot,
    phase: turn.phase,
    constraints: turn.constraints,
    // Prefer turn.shortlist whenever provided (including []) so refine/remove refresh cards.
    shortlist: nextShortlist,
    citations: turn.citations != null ? turn.citations : snapshot.citations,
    booking: turn.booking ?? snapshot.booking,
    selected_listing_id: keepSelected
      ? snapshot.selected_listing_id
      : nextShortlist[0]?.listing.listing_id ?? null,
    turns: [
      ...snapshot.turns,
      { role: "user", text: userText, intent: null },
      { role: "assistant", text: turn.assistant_text, intent: null },
    ],
  };
}

export function applyConfirmResponse(
  snapshot: SessionSnapshot,
  turn: TurnResponse,
): SessionSnapshot {
  return {
    ...snapshot,
    phase: turn.phase,
    constraints: turn.constraints,
    shortlist: turn.shortlist != null ? turn.shortlist : snapshot.shortlist,
    citations: turn.citations != null ? turn.citations : snapshot.citations,
    booking: turn.booking ?? snapshot.booking,
    turns: [
      ...snapshot.turns,
      { role: "user", text: "[confirm-search]", intent: "confirm_search" },
      { role: "assistant", text: turn.assistant_text, intent: "confirm_search" },
    ],
  };
}

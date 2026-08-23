/** Shared TypeScript mirrors of API domain schemas (Phase 0). */

export type {
  HardConstraints,
  SoftPreferences,
  Constraints,
  Listing,
  RankResult,
  Citation,
  SessionPhase,
  ShortlistItem,
  Booking,
  ConversationTurn,
  SessionSnapshot,
  TurnRequest,
  TurnResponse,
  OsmPoi,
  OsmContext,
  NeighborhoodNote,
} from "./session";

export type PreferencePatch = {
  hard?: import("./session").HardConstraints | null;
  soft?: import("./session").SoftPreferences | null;
  commute_point?: string | null;
  patch_mode: "merge";
};

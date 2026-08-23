/** Session-focused TypeScript mirrors (Phase 0). */

export type SessionPhase =
  | "clarifying"
  | "awaiting_confirm"
  | "shortlist"
  | "booking"
  | "idle";

export type HardConstraints = {
  bedrooms?: number | null;
  locality?: string | null;
  max_rent?: number | null;
  must_have_amenities: string[];
};

export type SoftPreferences = {
  near_metro?: boolean | null;
  pet_friendly?: boolean | null;
  balcony?: boolean | null;
};

export type Constraints = {
  hard: HardConstraints;
  soft: SoftPreferences;
  commute_point?: string | null;
};

export type Listing = {
  listing_id: string;
  source_url: string;
  location: string;
  locality: string;
  rent: number;
  bedrooms: number;
  furnishing: string;
  amenities: string[];
  society_name: string;
  square_footage: number;
  available_from: string;
  deposit_amount: number;
  listing_type: "whole flat" | "room in a flat" | string;
  food_preference: "veg" | "non-veg" | "any" | string;
  smoking_preference: "no smoking" | "smoking allowed" | "any" | string;
  gender?: "male" | "female" | "any" | string | null;
  neighborhood_guidance: {
    locality: string;
    safety: string;
    amenities: string;
    transit_character: string;
    sources: Array<{ title: string; url: string; snippet?: string }>;
  };
  availability_status: string;
  latitude: number;
  longitude: number;
};

export type ListingDaySnapshot = {
  listing_id: string;
  as_of_date: string;
  rent: number;
  deposit_amount: number;
  availability_status: string;
};

export type ListingSnapshotSeries = {
  listing_id: string;
  days: number;
  snapshots: ListingDaySnapshot[];
};

export type RankResult = {
  listing_id: string;
  score: number;
  matched: string[];
  missing: string[];
  excluded: boolean;
  exclusion_reasons: string[];
  reason: string;
};

export type Citation = {
  id: string;
  title: string;
  url: string;
  snippet: string;
  locality?: string | null;
  topic?: string | null;
};

export type OsmPoi = {
  name: string;
  category: string;
  lat: number;
  lon: number;
  distance_m?: number | null;
};

export type OsmContext = {
  listing_id: string;
  pois: OsmPoi[];
  raw_call_id: string;
  empty_reason?: string | null;
};

export type NeighborhoodNote = {
  topic: string;
  text: string;
  citation_id: string;
};

export type ShortlistItem = {
  listing: Listing;
  rank: RankResult;
  citations: Citation[];
  osm?: OsmContext | null;
  neighborhood_notes?: NeighborhoodNote[];
};

export type Booking = {
  listing_id: string;
  date: string;
  slot: string;
  status: "pending" | "confirmed" | "cancelled";
  confirmation_code?: string | null;
};

export type ConversationTurn = {
  role: "user" | "assistant";
  text: string;
  intent?: string | null;
};

export type SessionSnapshot = {
  session_id: string;
  phase: SessionPhase;
  clarification_count: number;
  constraints: Constraints;
  shortlist: ShortlistItem[];
  citations: Citation[];
  booking?: Booking | null;
  turns: ConversationTurn[];
  selected_listing_id?: string | null;
};

export type TurnRequest = {
  text: string;
};

export type TurnResponse = {
  assistant_text: string;
  constraints: Constraints;
  shortlist?: ShortlistItem[] | null;
  citations?: Citation[] | null;
  booking?: Booking | null;
  phase: SessionPhase;
  /** WAV audio (base64) generated with the turn for synced playback */
  tts_audio_base64?: string | null;
};

import type { OsmPoi, ShortlistItem } from "@property-scout/schemas";
import { isWikipediaUrl } from "@/lib/citations";

export function formatScore(score: number): number {
  return score <= 1 ? Math.round(score * 100) : Math.round(score);
}

export function formatMatchScoreLabel(score: number): string {
  return `${formatScore(score)}% Match`;
}

export function formatListingHeadline(item: ShortlistItem): string {
  const { listing } = item;
  return [
    listing.society_name,
    listing.locality,
    `${listing.bedrooms} BHK`,
    `₹${listing.rent.toLocaleString("en-IN")}/mo`,
    `${Math.round(listing.square_footage)} sq ft`,
    listing.furnishing,
  ].join(" · ");
}

export function formatMatched(matched: string[]): string {
  return matched.join(", ");
}

function noteForTopic(item: ShortlistItem, topic: string): string | null {
  const note = item.neighborhood_notes?.find((n) => n.topic === topic);
  return note?.text?.trim() || null;
}

export type NeighborhoodCardLines = {
  safety: string;
  transit: string;
  amenities: string;
  poi: string | null;
  cited: boolean;
};

export function neighborhoodLines(item: ShortlistItem): NeighborhoodCardLines {
  const guidance = item.listing.neighborhood_guidance;
  const notes = item.neighborhood_notes ?? [];
  const guidanceSources = guidance.sources.filter((s) => s.url && !isWikipediaUrl(s.url));
  const cited =
    notes.some(
      (n) =>
        n.citation_id &&
        n.citation_id !== "unverified" &&
        n.citation_id !== "listing" &&
        n.citation_id !== "listing-guidance" &&
        n.citation_id !== "listing+osm" &&
        n.citation_id !== "osm",
    ) || guidanceSources.length > 0;

  return {
    safety: noteForTopic(item, "safety") ?? guidance.safety,
    transit: noteForTopic(item, "transit") ?? guidance.transit_character,
    amenities: noteForTopic(item, "amenities") ?? guidance.amenities,
    poi: formatPoiLine(item.osm?.pois ?? []),
    cited,
  };
}

function formatPoiLine(pois: OsmPoi[]): string | null {
  if (!pois.length) return null;

  const picked: OsmPoi[] = [];
  for (const category of ["metro", "grocery", "transit", "park", "restaurant"] as const) {
    const poi = pois.find((p) => p.category === category);
    if (poi && !picked.includes(poi)) picked.push(poi);
  }
  for (const poi of pois) {
    if (picked.length >= 4) break;
    if (!picked.includes(poi)) picked.push(poi);
  }

  const parts = picked.map((poi) => {
    const dist =
      poi.distance_m != null ? ` (~${Math.round(poi.distance_m)}m)` : "";
    const name =
      poi.name && !poi.name.toLowerCase().startsWith("unnamed")
        ? ` ${poi.name}`
        : "";
    return `${poi.category}${name}${dist}`;
  });

  return parts.length ? parts.join(", ") : null;
}

import type { Citation, ShortlistItem } from "@property-scout/schemas";

export function isWikipediaUrl(url: string): boolean {
  return url.toLowerCase().includes("wikipedia.org");
}

export function listingSourceCitation(item: ShortlistItem): Citation | null {
  const { listing } = item;
  if (!listing?.source_url) return null;
  const rentInr = listing.rent ? `₹${listing.rent.toLocaleString("en-IN")}` : "rent details";
  return {
    id: `listing-${listing.listing_id}`,
    title: "bengaluru.rent — listing",
    url: listing.source_url,
    snippet: `Listing on bengaluru.rent — ${listing.locality}, ${listing.bedrooms} BHK, ${rentInr}/month.`,
    locality: listing.locality,
    topic: "listing",
  };
}

export function osmCitation(item: ShortlistItem): Citation | null {
  const { listing, osm } = item;
  if (!listing || !osm) return null;
  const { latitude, longitude } = listing;
  const url = `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=16/${latitude}/${longitude}`;
  const poiCount = osm.pois?.length ?? 0;
  const snippet = poiCount
    ? `${poiCount} nearby POIs from OpenStreetMap (transit, amenities, and more).`
    : osm.empty_reason ?? "OpenStreetMap data for transit and amenities near this listing.";
  return {
    id: `osm-${osm.raw_call_id}`,
    title: "OpenStreetMap — nearby POIs",
    url,
    snippet,
    locality: listing.locality,
    topic: "osm",
  };
}

/** Sources panel: bengaluru.rent + OSM; never Wikipedia. */
export function sourcesForItem(
  item: ShortlistItem | null,
  sessionCitations: Citation[],
): Citation[] {
  const merged = new Map<string, Citation>();

  if (item) {
    for (const cite of [listingSourceCitation(item), osmCitation(item)]) {
      if (cite?.url) merged.set(cite.url, cite);
    }
    for (const cite of item.citations ?? []) {
      if (!cite.url || isWikipediaUrl(cite.url) || merged.has(cite.url)) continue;
      merged.set(cite.url, cite);
    }
  }

  for (const cite of sessionCitations) {
    if (!cite.url || isWikipediaUrl(cite.url) || merged.has(cite.url)) continue;
    merged.set(cite.url, cite);
  }

  return Array.from(merged.values());
}

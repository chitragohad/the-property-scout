import type { ShortlistItem } from "@property-scout/schemas";
import styles from "./companion.module.css";
import {
  formatListingHeadline,
  formatMatchScoreLabel,
  formatMatched,
  formatScore,
  neighborhoodLines,
} from "@/lib/shortlist-format";

type Props = {
  items: ShortlistItem[];
  selectedId: string | null;
  onSelect: (listingId: string) => void;
  showHeader?: boolean;
};

export function ShortlistCards({
  items,
  selectedId,
  onSelect,
  showHeader = true,
}: Props) {
  return (
    <section aria-labelledby="shortlist-heading">
      {showHeader && (
        <header className={styles.shortlistHeader}>
          <h2 id="shortlist-heading">Curated Shortlist</h2>
          <p>
            {items.length === 0
              ? "Confirm your preferences to search available listings."
              : `Showing ${items.length} top match${items.length === 1 ? "" : "es"} based on your criteria.`}
          </p>
        </header>
      )}

      {items.length === 0 ? (
        <p className={styles.empty}>
          No shortlisted homes yet. Complete your search on the Home tab.
        </p>
      ) : (
        <ul className={styles.cardList}>
          {items.map((item) => {
            const { listing, rank } = item;
            const selected = listing.listing_id === selectedId;
            const hood = neighborhoodLines(item);

            return (
              <li key={listing.listing_id}>
                <button
                  type="button"
                  className={styles.card}
                  data-selected={selected || undefined}
                  onClick={() => onSelect(listing.listing_id)}
                  aria-pressed={selected}
                >
                  <div className={styles.cardBody}>
                    <div className={styles.cardHeadlineRow}>
                      <p className={styles.cardHeadline}>{formatListingHeadline(item)}</p>
                      <span className={styles.matchBadge}>
                        {formatMatchScoreLabel(rank.score)}
                      </span>
                    </div>

                    <p className={styles.cardScoreLine}>
                      <span className={styles.cardLabel}>Score:</span>{" "}
                      <span className={styles.cardScoreValue}>{formatScore(rank.score)}</span>
                      {rank.matched.length > 0 && (
                        <>
                          <span className={styles.cardSep}>·</span>
                          <span className={styles.cardLabel}>Matched:</span>{" "}
                          {formatMatched(rank.matched)}
                        </>
                      )}
                    </p>

                    <p className={styles.cardWhyLine}>
                      <span className={styles.cardLabel}>Why:</span> {rank.reason}
                    </p>

                    <div className={styles.cardNeighborhood}>
                      <p className={styles.cardNeighborhoodTitle}>
                        Neighborhood{hood.cited ? " (cited)" : ""}
                      </p>
                      <p className={styles.cardNeighborhoodRow}>
                        <span className={styles.cardLabel}>Safety:</span> {hood.safety}
                      </p>
                      <p className={styles.cardNeighborhoodRow}>
                        <span className={styles.cardLabel}>Transit:</span> {hood.transit}
                      </p>
                      <p className={styles.cardNeighborhoodRow}>
                        <span className={styles.cardLabel}>Amenities:</span> {hood.amenities}
                      </p>
                      {hood.poi && (
                        <p className={styles.cardNeighborhoodRow}>
                          <span className={styles.cardLabel}>POI:</span> {hood.poi}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

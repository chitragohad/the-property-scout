import type { Citation, ShortlistItem } from "@property-scout/schemas";
import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";
import { sourcesForItem } from "@/lib/citations";

type Props = {
  item: ShortlistItem | null;
  sessionCitations: Citation[];
};

export function SourcesPanel({ item, sessionCitations }: Props) {
  const citations = sourcesForItem(item, sessionCitations);

  return (
    <section className={styles.panel} aria-labelledby="sources-heading">
      <div className={styles.panelHeader}>
        <h2 id="sources-heading">
          <MaterialIcon name="menu_book" />
          Sources
        </h2>
      </div>
      {citations.length === 0 ? (
        <p className={styles.empty}>No public sources cited yet.</p>
      ) : (
        <ul className={styles.sourceLinkList}>
          {citations.map((cite) => (
            <li key={cite.url}>
              <a href={cite.url} target="_blank" rel="noopener noreferrer">
                {cite.title}
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

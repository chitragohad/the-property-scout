import type { Constraints, SessionPhase } from "@property-scout/schemas";
import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

type Props = {
  constraints: Constraints;
  phase: SessionPhase;
  clarificationCount: number;
  insight?: string | null;
};

function fmt(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function hasPreferences(constraints: Constraints): boolean {
  const { hard, soft } = constraints;
  return !!(
    hard.bedrooms ||
    hard.locality ||
    hard.max_rent ||
    hard.must_have_amenities.length ||
    soft.near_metro != null ||
    soft.balcony != null ||
    soft.pet_friendly != null ||
    constraints.commute_point
  );
}

export function PreferenceSummary({
  constraints,
  phase,
  clarificationCount,
  insight,
}: Props) {
  const { hard, soft } = constraints;
  const filled = hasPreferences(constraints);

  return (
    <section className={`${styles.panel} ${styles.panelSticky}`} aria-labelledby="prefs-heading">
      <div className={styles.panelHeader}>
        <h2 id="prefs-heading">
          <MaterialIcon name="tune" />
          Preferences
        </h2>
      </div>

      {!filled ? (
        <div className={styles.prefEmpty}>
          <MaterialIcon name="tune" size={40} />
          <p>We&apos;ll build your search profile here as we chat.</p>
          <div className={styles.prefChips}>
            <div className={styles.prefChipPlaceholder}>
              <span>Location</span>
              <span>Where to?</span>
            </div>
            <div className={styles.prefChipPlaceholder}>
              <span>Bedrooms</span>
              <span>2BHK?</span>
            </div>
            <div className={styles.prefChipPlaceholder}>
              <span>Budget</span>
              <span>Max rent?</span>
            </div>
            <div className={styles.prefChipPlaceholder}>
              <span>Must-haves</span>
              <span>Parking, gym…</span>
            </div>
          </div>
        </div>
      ) : (
        <dl className={styles.prefBento}>
          {hard.locality && (
            <div className={styles.prefItem}>
              <div className={styles.prefItemIcon}>
                <MaterialIcon name="location_on" />
              </div>
              <div>
                <dt>Locality</dt>
                <dd>{fmt(hard.locality)}</dd>
              </div>
            </div>
          )}
          {hard.bedrooms != null && (
            <div className={styles.prefItem}>
              <div className={styles.prefItemIcon}>
                <MaterialIcon name="bed" />
              </div>
              <div>
                <dt>Bedrooms</dt>
                <dd>{hard.bedrooms} BHK</dd>
              </div>
            </div>
          )}
          {hard.max_rent != null && (
            <div className={styles.prefItem}>
              <div className={styles.prefItemIcon}>
                <MaterialIcon name="payments" />
              </div>
              <div>
                <dt>Max Rent</dt>
                <dd>₹{hard.max_rent.toLocaleString("en-IN")}</dd>
              </div>
            </div>
          )}
          {hard.must_have_amenities.length > 0 && (
            <div className={styles.prefItem}>
              <div className={styles.prefItemIcon}>
                <MaterialIcon name="checklist" />
              </div>
              <div>
                <dt>Must-have</dt>
                <dd>{hard.must_have_amenities.join(", ")}</dd>
              </div>
            </div>
          )}
          {soft.near_metro != null && (
            <div className={styles.prefItem}>
              <div className={styles.prefItemIcon}>
                <MaterialIcon name="train" />
              </div>
              <div>
                <dt>Near metro</dt>
                <dd>{fmt(soft.near_metro)}</dd>
              </div>
            </div>
          )}
          {soft.pet_friendly != null && (
            <div className={styles.prefItem}>
              <div className={styles.prefItemIcon}>
                <MaterialIcon name="pets" />
              </div>
              <div>
                <dt>Pet friendly</dt>
                <dd>{fmt(soft.pet_friendly)}</dd>
              </div>
            </div>
          )}
        </dl>
      )}

      {insight && (
        <div className={styles.prefInsight}>
          <div className={styles.prefInsightBox}>&ldquo;{insight}&rdquo;</div>
        </div>
      )}

      {phase === "clarifying" && (
        <p className={styles.hint}>
          Clarifications used: {clarificationCount} / 5
        </p>
      )}
    </section>
  );
}

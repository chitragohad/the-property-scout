import type { Constraints } from "@property-scout/schemas";
import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

export function ActivePreferencesCompact({ constraints }: { constraints: Constraints }) {
  const { hard } = constraints;

  return (
    <div className={`${styles.panel} ${styles.compactPrefs}`}>
      <div className={styles.panelHeader}>
        <h3>
          <MaterialIcon name="tune" />
          Active Preferences
        </h3>
      </div>
      <ul>
        <li>
          <span>Budget</span>
          <span className={styles.mono}>
            {hard.max_rent != null
              ? `≤ ₹${hard.max_rent.toLocaleString("en-IN")}`
              : "—"}
          </span>
        </li>
        <li>
          <span>Configuration</span>
          <span>{hard.bedrooms != null ? `${hard.bedrooms} BHK` : "—"}</span>
        </li>
        <li>
          <span>Locality</span>
          <span>{hard.locality || "—"}</span>
        </li>
        {hard.must_have_amenities.length > 0 && (
          <li>
            <span>Must Haves</span>
            <div className={styles.tagRow}>
              {hard.must_have_amenities.map((a) => (
                <span key={a} className={styles.tag}>
                  {a}
                </span>
              ))}
            </div>
          </li>
        )}
      </ul>
    </div>
  );
}

"use client";

import type { Constraints } from "@property-scout/schemas";
import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

type Props = {
  constraints: Constraints;
  disabled?: boolean;
  onConfirm: () => void;
};

function fmtRent(value: number | null | undefined): string {
  if (value == null) return "—";
  return `₹${value.toLocaleString("en-IN")}`;
}

export function ConfirmSearchCard({ constraints, disabled, onConfirm }: Props) {
  const { hard } = constraints;
  const bedrooms =
    hard.bedrooms != null ? `${hard.bedrooms} BHK` : "—";
  const locality = hard.locality || "—";
  const mustHaves =
    hard.must_have_amenities.length > 0
      ? hard.must_have_amenities.join(", ")
      : null;

  return (
    <div className={styles.confirmCard}>
      <div className={styles.confirmCardHeader}>
        <h2 className={styles.confirmCardTitle}>Search Criteria Parameters</h2>
        <span className={styles.readyBadge}>Ready</span>
      </div>

      <dl className={styles.confirmGrid}>
        <div>
          <dt>Locality</dt>
          <dd>
            <MaterialIcon name="location_on" />
            <span>{locality}</span>
          </dd>
        </div>
        <div>
          <dt>Configuration</dt>
          <dd>
            <MaterialIcon name="bed" />
            <span>{bedrooms}</span>
          </dd>
        </div>
        <div className={styles.confirmGridFull}>
          <dt>Max Budget</dt>
          <dd className={styles.confirmRent}>
            {fmtRent(hard.max_rent)}
            <span className={styles.rentSuffix}>/mo</span>
          </dd>
        </div>
      </dl>

      {mustHaves && (
        <p className={styles.confirmNote}>
          Must-haves: {mustHaves}
        </p>
      )}

      <div className={styles.confirmCtaWrap}>
        <button
          type="button"
          className={styles.confirmCta}
          disabled={disabled}
          onClick={onConfirm}
        >
          Confirm Search
          <MaterialIcon name="arrow_forward" />
        </button>
      </div>
    </div>
  );
}

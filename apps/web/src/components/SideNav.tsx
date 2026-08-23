"use client";

import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

export type NavTab = "home" | "shortlist" | "history";

type Props = {
  activeTab: NavTab;
  shortlistCount: number;
  onTabChange: (tab: NavTab) => void;
  onNewSearch: () => void;
  newSearchDisabled?: boolean;
};

export function SideNav({
  activeTab,
  shortlistCount,
  onTabChange,
  onNewSearch,
  newSearchDisabled,
}: Props) {
  return (
    <nav className={styles.sideNav} aria-label="Main navigation">
      <div className={styles.sideNavBrand}>
        <h1 className={styles.sideNavTitle}>Property Scout</h1>
        <p className={styles.sideNavTagline}>Your Real Estate Advisor</p>
      </div>

      <ul className={styles.sideNavLinks}>
        <li>
          <button
            type="button"
            className={styles.sideNavLink}
            data-active={activeTab === "home" ? "true" : undefined}
            onClick={() => onTabChange("home")}
          >
            <MaterialIcon name="home" filled={activeTab === "home"} />
            <span>Home</span>
          </button>
        </li>
        <li>
          <button
            type="button"
            className={styles.sideNavLink}
            data-active={activeTab === "shortlist" ? "true" : undefined}
            onClick={() => onTabChange("shortlist")}
          >
            <MaterialIcon name="favorite" filled={activeTab === "shortlist"} />
            <span>
              Shortlist
              {shortlistCount > 0 && (
                <span className={styles.navBadge}>{shortlistCount}</span>
              )}
            </span>
          </button>
        </li>
        <li>
          <button
            type="button"
            className={styles.sideNavLink}
            data-active={activeTab === "history" ? "true" : undefined}
            onClick={() => onTabChange("history")}
          >
            <MaterialIcon name="history" filled={activeTab === "history"} />
            <span>History</span>
          </button>
        </li>
      </ul>

      <div className={styles.sideNavFooter}>
        <button
          type="button"
          className={styles.newSearchBtn}
          onClick={onNewSearch}
          disabled={newSearchDisabled}
        >
          New Search
        </button>
      </div>
    </nav>
  );
}

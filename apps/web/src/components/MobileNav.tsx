"use client";

import { MaterialIcon } from "./MaterialIcon";
import type { NavTab } from "./SideNav";
import styles from "./companion.module.css";

type Props = {
  activeTab: NavTab;
  shortlistCount: number;
  onTabChange: (tab: NavTab) => void;
};

export function MobileNav({ activeTab, shortlistCount, onTabChange }: Props) {
  return (
    <nav className={styles.mobileNav} aria-label="Mobile navigation">
      <button
        type="button"
        className={styles.mobileNavBtn}
        data-active={activeTab === "home" ? "true" : undefined}
        onClick={() => onTabChange("home")}
      >
        <MaterialIcon name="home" filled={activeTab === "home"} />
        <span>Home</span>
      </button>
      <button
        type="button"
        className={styles.mobileNavBtn}
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
      <button
        type="button"
        className={styles.mobileNavBtn}
        data-active={activeTab === "history" ? "true" : undefined}
        onClick={() => onTabChange("history")}
      >
        <MaterialIcon name="history" filled={activeTab === "history"} />
        <span>History</span>
      </button>
    </nav>
  );
}

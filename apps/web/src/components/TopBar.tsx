import type { SessionPhase } from "@property-scout/schemas";
import { MaterialIcon } from "./MaterialIcon";
import { PhaseBadge } from "./PhaseBadge";
import styles from "./companion.module.css";

type Props = {
  phase: SessionPhase;
  apiOk: boolean | null;
  ttsSupported?: boolean;
  ttsOn?: boolean;
  onTtsToggle?: () => void;
};

export function TopBar({ phase, apiOk, ttsSupported, ttsOn, onTtsToggle }: Props) {
  return (
    <header className={styles.topBar}>
      <div className={styles.topBarLeft}>
        <PhaseBadge phase={phase} />
        <span className={styles.apiStatus} data-ok={apiOk === true ? "true" : undefined}>
          <span className={styles.statusDot} aria-hidden />
          {apiOk === null ? "Connecting…" : apiOk ? "Connected" : "Offline"}
        </span>
      </div>
      <div className={styles.topBarRight}>
        {ttsSupported && onTtsToggle && (
          <button
            type="button"
            className={styles.iconBtn}
            onClick={onTtsToggle}
            aria-pressed={ttsOn}
            title={ttsOn ? "Disable spoken replies" : "Enable spoken replies"}
          >
            <MaterialIcon name={ttsOn ? "volume_up" : "volume_off"} />
          </button>
        )}
        <button type="button" className={styles.iconBtn} title="Help">
          <MaterialIcon name="help" />
        </button>
      </div>
    </header>
  );
}

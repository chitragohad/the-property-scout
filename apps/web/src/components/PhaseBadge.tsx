import type { SessionPhase } from "@property-scout/schemas";
import styles from "./companion.module.css";

type Props = {
  phase: SessionPhase;
};

const LABELS: Record<SessionPhase, string> = {
  idle: "Idle",
  clarifying: "Clarifying",
  awaiting_confirm: "Awaiting confirm",
  shortlist: "Shortlist",
  booking: "Booking",
};

export function PhaseBadge({ phase }: Props) {
  return (
    <span className={styles.phaseBadgePill} data-phase={phase}>
      <span className={styles.phaseDot} aria-hidden />
      {LABELS[phase]}
    </span>
  );
}

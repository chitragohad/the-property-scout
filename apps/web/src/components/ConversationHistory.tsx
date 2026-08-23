import type { ConversationTurn } from "@property-scout/schemas";
import styles from "./companion.module.css";

type Props = {
  turns: ConversationTurn[];
  pending?: boolean;
  compact?: boolean;
};

export function ConversationHistory({ turns, pending, compact }: Props) {
  const visible = turns.filter(
    (t) => t.text !== "[confirm-search]" && t.text !== "[email-shortlist]",
  );

  if (visible.length === 0 && !pending) {
    return null;
  }

  return (
    <section
      className={compact ? undefined : styles.panel}
      aria-labelledby="chat-heading"
    >
      {!compact && <h2 id="chat-heading" className={styles.srOnly}>Conversation</h2>}
      <div className={styles.chatLog} role="log" aria-live="polite">
        {visible.map((turn, index) => (
          <article
            key={`${turn.role}-${index}-${turn.text.slice(0, 24)}`}
            className={styles.chatBubble}
            data-role={turn.role}
          >
            {!compact && (
              <span className={styles.chatRole}>
                {turn.role === "user" ? "You" : "Scout"}
              </span>
            )}
            <p>{turn.text}</p>
            {turn.intent && turn.role === "user" && (
              <span className={styles.intentTag}>{turn.intent}</span>
            )}
          </article>
        ))}
        {pending && (
          <article className={styles.chatBubble} data-role="assistant">
            {!compact && <span className={styles.chatRole}>Scout</span>}
            <p className={styles.thinking}>Thinking…</p>
          </article>
        )}
      </div>
    </section>
  );
}

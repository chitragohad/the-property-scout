"use client";

import { useState } from "react";
import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

type Props = {
  disabled?: boolean;
  listingCount: number;
  deliveryEnabled?: boolean;
  onSubmit: (email: string) => Promise<{
    ok: boolean;
    message: string;
    delivered?: boolean;
  }>;
};

export function EmailShortlistPanel({
  disabled,
  listingCount,
  deliveryEnabled = false,
  onSubmit,
}: Props) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{
    kind: "success" | "warning" | "error";
    text: string;
  } | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (disabled || busy) return;

    const trimmed = email.trim();
    if (!trimmed) {
      setFeedback({ kind: "error", text: "Enter your email address." });
      return;
    }

    setBusy(true);
    setFeedback(null);
    try {
      const result = await onSubmit(trimmed);
      setFeedback({
        kind: result.ok
          ? result.delivered
            ? "success"
            : "warning"
          : "error",
        text: result.message,
      });
    } catch (err) {
      setFeedback({
        kind: "error",
        text: err instanceof Error ? err.message : "Could not send email.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.emailPanel} aria-labelledby="email-shortlist-heading">
      <div className={styles.emailPanelHeader}>
        <h2 id="email-shortlist-heading">
          <MaterialIcon name="mail" />
          Email this shortlist
        </h2>
        <p>
          We&apos;ll send {listingCount} listing{listingCount === 1 ? "" : "s"} with
          scores, neighborhood notes, and sources to your inbox
          {deliveryEnabled ? " via n8n" : ""}.
        </p>
      </div>

      <form className={styles.emailForm} onSubmit={handleSubmit}>
        <label className={styles.emailLabel} htmlFor="shortlist-email">
          Email address
        </label>
        <div className={styles.emailRow}>
          <input
            id="shortlist-email"
            type="email"
            autoComplete="email"
            inputMode="email"
            placeholder="you@example.com"
            className={styles.emailInput}
            value={email}
            disabled={disabled || busy}
            onChange={(event) => setEmail(event.target.value)}
          />
          <button
            type="submit"
            className={styles.emailButton}
            disabled={disabled || busy}
          >
            {busy ? "Sending…" : "Email me"}
            {!busy && <MaterialIcon name="send" />}
          </button>
        </div>
      </form>

      {feedback && (
        <p
          className={styles.emailFeedback}
          data-kind={feedback.kind}
          role="status"
        >
          {feedback.text}
        </p>
      )}
    </section>
  );
}

"use client";

import type { FormEvent } from "react";
import type { SessionPhase } from "@property-scout/schemas";
import { unlockSpeechAudio } from "@/lib/tts";
import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

type Props = {
  phase: SessionPhase;
  disabled?: boolean;
  onSubmit: (text: string) => void;
  listening?: boolean;
  sttSupported?: boolean;
  onMicClick?: () => void;
  micLabel?: string;
  docked?: boolean;
};

export function TurnInput({
  phase,
  disabled,
  onSubmit,
  listening,
  sttSupported,
  onMicClick,
  micLabel = "Start voice input",
  docked = true,
}: Props) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("message") as HTMLInputElement;
    const text = input.value.trim();
    if (!text || disabled) return;
    unlockSpeechAudio();
    onSubmit(text);
    input.value = "";
  };

  const placeholder =
    phase === "shortlist"
      ? "Refine by voice… e.g. 'under 30000' or 'remove the first one'"
      : phase === "awaiting_confirm"
        ? "Type or speak…"
        : "Type your preferences or ask a question…";

  const form = (
    <form className={styles.turnPill} onSubmit={handleSubmit}>
      <label htmlFor="turn-message" className={styles.srOnly}>
        Message
      </label>
      <input
        id="turn-message"
        name="message"
        type="text"
        className={styles.turnInput}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
      />
      {sttSupported && onMicClick && (
        <button
          type="button"
          className={styles.micBtnRound}
          data-recording={listening ? "true" : undefined}
          onClick={onMicClick}
          disabled={disabled}
          aria-pressed={listening}
          aria-label={micLabel}
        >
          <MaterialIcon name="mic" size={18} />
        </button>
      )}
    </form>
  );

  if (!docked) {
    return form;
  }

  return (
    <div className={styles.inputDock} aria-labelledby="turn-heading">
      <h2 id="turn-heading" className={styles.srOnly}>
        Send a message
      </h2>
      <div className={styles.inputDockInner}>
        {form}
        <p className={styles.inputHint}>
          {sttSupported ? "Tap mic to speak" : "Voice-first discovery enabled"}
        </p>
      </div>
    </div>
  );
}

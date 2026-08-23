"use client";

import { MaterialIcon } from "./MaterialIcon";
import styles from "./companion.module.css";

type Props = {
  disabled?: boolean;
  listening?: boolean;
  liveTranscript?: string;
  voiceHint?: string | null;
  sttSupported?: boolean;
  micLabel?: string;
  onMicClick?: () => void;
  welcomeMessage?: string;
};

export function VoiceHero({
  disabled,
  listening,
  liveTranscript,
  voiceHint,
  sttSupported = true,
  micLabel = "Start voice input",
  onMicClick,
  welcomeMessage = "How can I help you find your next home in Bengaluru?",
}: Props) {
  const prompt =
    liveTranscript ||
    welcomeMessage;

  return (
    <section className={styles.voiceHero} aria-labelledby="voice-hero-heading">
      <h2 id="voice-hero-heading" className={styles.srOnly}>
        Voice search
      </h2>

      {!sttSupported ? (
        <p className={styles.empty}>
          Voice input needs Chrome or Safari. Use the text field below instead.
        </p>
      ) : (
        <div className={styles.voiceHeroInner}>
          <button
            type="button"
            className={styles.heroMicBtn}
            data-recording={listening ? "true" : undefined}
            onClick={onMicClick}
            disabled={disabled}
            aria-pressed={listening}
            aria-label={micLabel}
          >
            <MaterialIcon name="mic" size={48} />
          </button>

          <div className={styles.heroPrompt}>
            <MaterialIcon name="assistant" className={styles.heroPromptIcon} />
            <p>{prompt}</p>
          </div>

          <p className={styles.heroHint}>
            {listening
              ? "Listening… tap mic again when you're done"
              : "Tap to speak or type your preferences"}
          </p>
        </div>
      )}

      {voiceHint && (
        <p className={styles.voiceHint} role="status">
          {voiceHint}
        </p>
      )}
    </section>
  );
}

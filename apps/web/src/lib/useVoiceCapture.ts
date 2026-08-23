"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchSttTranscript } from "@/lib/api";
import {
  SpeechTranscriber,
  evaluateTranscript,
  isSttSupported,
  type SttStatus,
} from "@/lib/stt";
import {
  isTtsSupported,
  loadVoiceConfig,
  setTtsEnabled,
  speakNow,
  stopSpeaking,
  unlockSpeechAudio,
} from "@/lib/tts";

type Options = {
  disabled?: boolean;
  onSubmit: (text: string) => void;
};

export function useVoiceCapture({ disabled, onSubmit }: Options) {
  const transcriber = useMemo(() => new SpeechTranscriber("en-IN"), []);
  const [status, setStatus] = useState<SttStatus>(
    transcriber.supported ? "idle" : "unsupported",
  );
  const [liveTranscript, setLiveTranscript] = useState("");
  const [voiceHint, setVoiceHint] = useState<string | null>(null);
  const [ttsOn, setTtsOn] = useState(true);
  const [ttsSupported, setTtsSupported] = useState(false);
  const submittedRef = useRef(false);
  const confidenceThresholdRef = useRef(0.6);

  useEffect(() => {
    transcriber.setServerTranscriber(fetchSttTranscript);
    // Ensure spoken replies are on — prior debugging may have left mute in storage.
    setTtsEnabled(true);
    setTtsOn(true);
    setTtsSupported(
      typeof window !== "undefined" &&
        ("speechSynthesis" in window || isTtsSupported()),
    );
    void loadVoiceConfig().then((cfg) => {
      confidenceThresholdRef.current = cfg.confidence_threshold;
      setTtsSupported(
        typeof window !== "undefined" &&
          ("speechSynthesis" in window || isTtsSupported()),
      );
    });
  }, [transcriber]);

  useEffect(() => {
    return () => {
      transcriber.cancel();
      stopSpeaking();
    };
  }, [transcriber]);

  const handleTtsToggle = useCallback(() => {
    const next = !ttsOn;
    setTtsOn(next);
    setTtsEnabled(next);
    if (!next) {
      stopSpeaking();
      return;
    }
    unlockSpeechAudio();
    speakNow("Spoken replies are on.");
  }, [ttsOn]);

  const handleMicClick = useCallback(() => {
    if (disabled || !transcriber.supported) return;

    if (status === "listening") {
      transcriber.stop();
      return;
    }

    submittedRef.current = false;
    setVoiceHint(null);
    setLiveTranscript("");
    // Unlock Audio element in this gesture so the reply WAV can play after /turn.
    unlockSpeechAudio();
    stopSpeaking();

    transcriber.start({
      onInterim: (text) => setLiveTranscript(text),
      onFinal: (result) => {
        if (submittedRef.current) return;
        const verdict = evaluateTranscript(
          result.text,
          result.confidence,
          confidenceThresholdRef.current,
        );
        if (!verdict.ok) {
          submittedRef.current = false;
          setVoiceHint(verdict.reason);
          setLiveTranscript("");
          return;
        }
        submittedRef.current = true;
        setVoiceHint(null);
        setLiveTranscript(verdict.text);
        onSubmit(verdict.text);
        setLiveTranscript("");
      },
      onError: (message) => {
        setVoiceHint(message);
        setLiveTranscript("");
      },
      onStatus: setStatus,
    });
  }, [disabled, onSubmit, status, transcriber]);

  const listening = status === "listening";
  const micLabel = listening ? "Stop recording" : "Start voice input";

  return {
    listening,
    liveTranscript,
    voiceHint,
    ttsOn,
    sttSupported: isSttSupported(),
    ttsSupported,
    micLabel,
    handleMicClick,
    handleTtsToggle,
  };
}

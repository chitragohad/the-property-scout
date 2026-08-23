/** Browser speech-to-text via Web Speech API, with MediaRecorder + API fallback. */

export type SttStatus = "idle" | "listening" | "unsupported";

export type SttFinalResult = {
  text: string;
  confidence: number | null;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      [alt: number]: { transcript: string; confidence?: number };
    };
  };
};

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  }
}

const MIN_CHARS = 3;
const NETWORK_RETRY_LIMIT = 2;
const RETRY_DELAY_MS = 280;
const START_DELAY_MS = 120;

export function isSttSupported(): boolean {
  if (typeof window === "undefined") return false;
  return (
    Boolean(window.SpeechRecognition ?? window.webkitSpeechRecognition) ||
    isMediaCaptureSupported()
  );
}

export function isMediaCaptureSupported(): boolean {
  if (typeof window === "undefined") return false;
  return (
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof MediaRecorder !== "undefined"
  );
}

/**
 * Validates transcript length and optional confidence from the Web Speech API.
 * Confidence is often 0 in Chrome — only reject when a positive score is below threshold.
 */
export function evaluateTranscript(
  text: string,
  confidence: number | null = null,
  confidenceThreshold = 0.6,
): { ok: true; text: string } | { ok: false; reason: string } {
  const trimmed = text.trim();
  if (
    confidence != null &&
    confidence > 0 &&
    confidence < confidenceThreshold
  ) {
    return {
      ok: false,
      reason: "I didn't catch that clearly. Please repeat your request.",
    };
  }
  if (trimmed.length < MIN_CHARS) {
    return {
      ok: false,
      reason: "I didn't catch that. Please repeat your request.",
    };
  }
  return { ok: true, text: trimmed };
}

export type SpeechTranscriberCallbacks = {
  onInterim: (text: string) => void;
  onFinal: (result: SttFinalResult) => void;
  onError: (message: string) => void;
  onStatus: (status: SttStatus) => void;
};

function getRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

function pickMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  for (const type of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return "audio/webm";
}

export class SpeechTranscriber {
  private recognition: SpeechRecognitionLike | null = null;
  private listening = false;
  private callbacks: SpeechTranscriberCallbacks | null = null;
  private accumulatedFinal = "";
  private pendingInterim = "";
  private lastConfidence: number | null = null;
  private flushed = false;
  private lang: string;
  private networkAttempts = 0;
  private startTimer: number | null = null;
  private preferMediaFallback = false;
  private mediaStream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private mediaChunks: BlobPart[] = [];
  private mediaMime = "audio/webm";
  private transcribeAudio:
    | ((blob: Blob) => Promise<string>)
    | null = null;

  constructor(lang = "en-IN") {
    this.lang = lang;
  }

  /** Optional server STT used when Chrome Web Speech returns network errors. */
  setServerTranscriber(fn: ((blob: Blob) => Promise<string>) | null): void {
    this.transcribeAudio = fn;
  }

  get supported(): boolean {
    return getRecognitionCtor() != null || isMediaCaptureSupported();
  }

  private resetBuffer(): void {
    this.accumulatedFinal = "";
    this.pendingInterim = "";
    this.lastConfidence = null;
    this.flushed = false;
  }

  private displayText(): string {
    return `${this.accumulatedFinal} ${this.pendingInterim}`.trim();
  }

  private flushFinal(callbacks: SpeechTranscriberCallbacks): void {
    if (this.flushed) return;
    const text = this.displayText();
    if (!text) return;
    this.flushed = true;
    callbacks.onFinal({ text, confidence: this.lastConfidence });
  }

  private clearStartTimer(): void {
    if (this.startTimer != null) {
      window.clearTimeout(this.startTimer);
      this.startTimer = null;
    }
  }

  private createRecognition(lang: string): SpeechRecognitionLike | null {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return null;
    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.maxAlternatives = 1;
    return recognition;
  }

  private wireRecognition(
    recognition: SpeechRecognitionLike,
    callbacks: SpeechTranscriberCallbacks,
  ): void {
    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const alt = result[0];
        const transcript = alt?.transcript ?? "";
        if (!transcript.trim()) continue;

        if (result.isFinal) {
          this.accumulatedFinal = `${this.accumulatedFinal} ${transcript}`.trim();
          this.pendingInterim = "";
          if (typeof alt?.confidence === "number") {
            this.lastConfidence = alt.confidence;
          }
        } else {
          this.pendingInterim = transcript.trim();
        }
      }

      const display = this.displayText();
      if (display) {
        callbacks.onInterim(display);
      }
    };

    recognition.onerror = (event) => {
      if (event.error === "aborted") {
        return;
      }

      if (
        (event.error === "network" || event.error === "service-not-allowed") &&
        this.networkAttempts < NETWORK_RETRY_LIMIT &&
        !this.preferMediaFallback
      ) {
        this.networkAttempts += 1;
        // Detach so onend does not treat this as a finished utterance.
        this.recognition = null;
        try {
          recognition.onend = null;
          recognition.onerror = null;
          recognition.abort();
        } catch {
          /* ignore */
        }
        window.setTimeout(() => {
          if (!this.listening || this.callbacks !== callbacks) return;
          const nextLang =
            this.networkAttempts >= 1 && this.lang.startsWith("en-")
              ? "en-US"
              : this.lang;
          this.beginWebSpeech(callbacks, nextLang);
        }, RETRY_DELAY_MS);
        return;
      }

      if (
        (event.error === "network" || event.error === "service-not-allowed") &&
        this.transcribeAudio &&
        isMediaCaptureSupported()
      ) {
        this.preferMediaFallback = true;
        this.recognition = null;
        try {
          recognition.onend = null;
          recognition.onerror = null;
          recognition.abort();
        } catch {
          /* ignore */
        }
        void this.beginMediaCapture(callbacks);
        return;
      }

      this.listening = false;
      this.recognition = null;
      callbacks.onStatus("idle");

      if (event.error === "no-speech") {
        this.flushFinal(callbacks);
        if (!this.flushed) {
          callbacks.onError("I didn't hear anything. Please try again.");
        }
        return;
      }
      if (event.error === "not-allowed") {
        callbacks.onError("Microphone access was blocked. Allow the mic and retry.");
        return;
      }
      if (event.error === "network") {
        callbacks.onError(
          "Speech capture failed (network). Check your connection, or type your preferences below.",
        );
        return;
      }
      callbacks.onError(`Speech capture failed (${event.error}). Please try again.`);
    };

    recognition.onend = () => {
      // Retries / media fallback null out recognition before ending.
      if (this.recognition !== recognition) return;
      this.listening = false;
      this.recognition = null;
      callbacks.onStatus("idle");
      this.flushFinal(callbacks);
    };
  }

  private beginWebSpeech(
    callbacks: SpeechTranscriberCallbacks,
    lang: string,
  ): void {
    const recognition = this.createRecognition(lang);
    if (!recognition) {
      if (this.transcribeAudio && isMediaCaptureSupported()) {
        void this.beginMediaCapture(callbacks);
        return;
      }
      this.listening = false;
      callbacks.onStatus("unsupported");
      callbacks.onError("Speech recognition is not supported in this browser.");
      return;
    }

    this.recognition = recognition;
    this.wireRecognition(recognition, callbacks);

    try {
      recognition.start();
    } catch {
      // Already started or engine busy — recreate once.
      try {
        recognition.abort();
      } catch {
        /* ignore */
      }
      const again = this.createRecognition(lang);
      if (!again) {
        this.listening = false;
        callbacks.onStatus("idle");
        callbacks.onError("Could not start the microphone. Wait a moment and retry.");
        return;
      }
      this.recognition = again;
      this.wireRecognition(again, callbacks);
      try {
        again.start();
      } catch {
        this.listening = false;
        this.recognition = null;
        callbacks.onStatus("idle");
        if (this.transcribeAudio && isMediaCaptureSupported()) {
          void this.beginMediaCapture(callbacks);
          return;
        }
        callbacks.onError("Could not start the microphone. Wait a moment and retry.");
      }
    }
  }

  private async beginMediaCapture(
    callbacks: SpeechTranscriberCallbacks,
  ): Promise<void> {
    if (!isMediaCaptureSupported() || !this.transcribeAudio) {
      this.listening = false;
      callbacks.onStatus("idle");
      callbacks.onError(
        "Speech capture failed (network). Please type your preferences below.",
      );
      return;
    }

    this.stopMediaTracks();
    callbacks.onStatus("listening");
    callbacks.onInterim("Listening… tap the mic when you’re done");

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaMime = pickMimeType();
      this.mediaChunks = [];
      this.mediaRecorder = new MediaRecorder(this.mediaStream, {
        mimeType: this.mediaMime,
      });

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) this.mediaChunks.push(event.data);
      };

      this.mediaRecorder.onerror = () => {
        this.listening = false;
        this.stopMediaTracks();
        callbacks.onStatus("idle");
        callbacks.onError("Microphone recording failed. Please try again or type below.");
      };

      this.mediaRecorder.start(250);
      this.listening = true;
    } catch {
      this.listening = false;
      this.stopMediaTracks();
      callbacks.onStatus("idle");
      callbacks.onError("Microphone access was blocked. Allow the mic and retry.");
    }
  }

  private stopMediaTracks(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      try {
        this.mediaRecorder.stop();
      } catch {
        /* ignore */
      }
    }
    this.mediaRecorder = null;
    if (this.mediaStream) {
      for (const track of this.mediaStream.getTracks()) {
        track.stop();
      }
      this.mediaStream = null;
    }
  }

  private async finishMediaCapture(
    callbacks: SpeechTranscriberCallbacks,
  ): Promise<void> {
    const recorder = this.mediaRecorder;
    const transcribe = this.transcribeAudio;
    if (!recorder || !transcribe) {
      this.listening = false;
      this.stopMediaTracks();
      callbacks.onStatus("idle");
      return;
    }

    const blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        resolve(new Blob(this.mediaChunks, { type: this.mediaMime }));
      };
      try {
        if (recorder.state !== "inactive") recorder.stop();
        else resolve(new Blob(this.mediaChunks, { type: this.mediaMime }));
      } catch {
        resolve(new Blob(this.mediaChunks, { type: this.mediaMime }));
      }
    });

    this.stopMediaTracks();
    this.listening = false;
    callbacks.onStatus("idle");

    if (blob.size < 800) {
      callbacks.onError("I didn't hear anything. Please try again.");
      return;
    }

    callbacks.onInterim("Transcribing…");
    try {
      const text = await transcribe(blob);
      const trimmed = text.trim();
      if (!trimmed) {
        callbacks.onError("I didn't catch that. Please repeat your request.");
        return;
      }
      callbacks.onFinal({ text: trimmed, confidence: null });
    } catch {
      callbacks.onError(
        "Speech capture failed (network). Please type your preferences below.",
      );
    }
  }

  start(callbacks: SpeechTranscriberCallbacks): void {
    if (this.listening) return;

    this.callbacks = callbacks;
    this.listening = true;
    this.networkAttempts = 0;
    this.resetBuffer();
    this.clearStartTimer();
    callbacks.onStatus("listening");

    // Brief pause after speechSynthesis.cancel() — Chrome otherwise returns network.
    this.startTimer = window.setTimeout(() => {
      this.startTimer = null;
      if (!this.listening || this.callbacks !== callbacks) return;

      if (this.preferMediaFallback && this.transcribeAudio) {
        void this.beginMediaCapture(callbacks);
        return;
      }

      if (getRecognitionCtor()) {
        this.beginWebSpeech(callbacks, this.lang);
        return;
      }

      if (this.transcribeAudio && isMediaCaptureSupported()) {
        void this.beginMediaCapture(callbacks);
        return;
      }

      this.listening = false;
      callbacks.onStatus("unsupported");
      callbacks.onError("Speech recognition is not supported in this browser.");
    }, START_DELAY_MS);
  }

  stop(): void {
    this.clearStartTimer();

    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      const callbacks = this.callbacks;
      if (callbacks) void this.finishMediaCapture(callbacks);
      return;
    }

    if (!this.recognition || !this.listening) return;
    try {
      this.recognition.stop();
    } catch {
      try {
        this.recognition.abort();
      } catch {
        /* ignore */
      }
    }
  }

  cancel(): void {
    this.clearStartTimer();
    this.flushed = true;
    this.listening = false;

    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch {
        /* ignore */
      }
      this.recognition = null;
    }

    this.stopMediaTracks();
    this.callbacks?.onStatus("idle");
  }
}

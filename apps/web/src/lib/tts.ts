/**
 * Text-to-speech for Property Scout.
 *
 * Turn replies: browser speech starts with the on-screen text (no /voice/tts wait).
 * Bundled base64 WAV from /turn plays instantly when present.
 * Server WAV is fallback only if browser speech does not start.
 */

import { fetchTtsAudio, fetchVoiceConfig, type VoiceConfig } from "@/lib/api";

const STORAGE_KEY = "property-scout-tts-enabled";
const BROWSER_CHUNK_MAX_CHARS = 480;
const MAX_SPEECH_CHARS = 420;
/** Only needed after cancelling an active utterance. */
const AFTER_CANCEL_MS = 80;
/** If browser speech has not started, fetch server WAV. */
const BROWSER_START_TIMEOUT_MS = 700;
const SYNTH_KEEPALIVE_MS = 10_000;

const SHORTLIST_REVEAL_RE = /I found \d+ options?/i;
const LISTING_LINE_RE = /\d+\.\s+.+?\d+\s*BHK/i;
const LISTING_SCORE_RE = /\(score\s[\d.]+\)/i;

type VoiceMode = "gemini" | "browser";

let voiceConfig: VoiceConfig | null = null;
let voiceConfigPromise: Promise<VoiceConfig> | null = null;
let preferredMode: VoiceMode | null = null;
let preferredModeInit: Promise<VoiceMode> | null = null;
let lockedBrowserVoice: SpeechSynthesisVoice | null = null;
let activeGeneration = 0;
let speaking = false;
let sharedAudio: HTMLAudioElement | null = null;
let sharedObjectUrl: string | null = null;
let synthKeepAliveTimer: number | null = null;
let pendingSpeakTimer: number | null = null;

function truncateForSpeech(text: string, maxChars = MAX_SPEECH_CHARS): string {
  if (text.length <= maxChars) return text;
  const cut = text.slice(0, maxChars);
  const boundary = Math.max(
    cut.lastIndexOf("."),
    cut.lastIndexOf("!"),
    cut.lastIndexOf("?"),
  );
  if (boundary >= 80) return cut.slice(0, boundary + 1).trim();
  return `${cut.trim()}…`;
}

export function getTtsEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === null) return true;
    return stored === "1";
  } catch {
    return true;
  }
}

export function setTtsEnabled(enabled: boolean): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
  } catch {
    /* ignore */
  }
}

/** Call from mic / confirm / send clicks so Audio.play() works after await. */
export function unlockSpeechAudio(): void {
  if (typeof window === "undefined") return;

  const silent = new Audio(
    "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAAAA==",
  );
  silent.volume = 0.01;
  void silent.play().catch(() => {});

  if ("speechSynthesis" in window) {
    try {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.resume();
    } catch {
      /* ignore */
    }
  }
}

/** @deprecated session keep-alive removed — Audio element is the async path. */
export function beginSpeechSession(): void {}
/** @deprecated */
export function endSpeechSession(): void {}

export function assistantTextForSpeech(
  assistantText: string,
  shortlistCount: number,
): string {
  const trimmed = assistantText.trim();
  if (!trimmed) return trimmed;

  if (shortlistCount > 0) {
    const listingLineCount = (trimmed.match(/\d+\.\s+/g) ?? []).length;
    const isShortlistReveal =
      SHORTLIST_REVEAL_RE.test(trimmed) ||
      /Here are the listings as per your request/i.test(trimmed) ||
      /I've updated the Shortlist tab/i.test(trimmed) ||
      LISTING_LINE_RE.test(trimmed) ||
      listingLineCount >= 2 ||
      (LISTING_SCORE_RE.test(trimmed) && listingLineCount >= 1);

    if (isShortlistReveal) {
      const countMatch = trimmed.match(/I found (\d+) options?/i);
      if (countMatch) {
        return `I found ${countMatch[1]} options. Here are the listings as per your request.`;
      }
      return "Here are the listings as per your request.";
    }
  }

  return truncateForSpeech(trimmed);
}

export function getVoiceConfig(): VoiceConfig | null {
  return voiceConfig;
}

export async function loadVoiceConfig(): Promise<VoiceConfig> {
  if (voiceConfig) return voiceConfig;
  if (!voiceConfigPromise) {
    voiceConfigPromise = fetchVoiceConfig()
      .then((cfg) => {
        voiceConfig = cfg;
        return cfg;
      })
      .catch(() => {
        const fallback: VoiceConfig = {
          gemini_tts_available: false,
          confidence_threshold: 0.6,
          voice: "Charon",
        };
        voiceConfig = fallback;
        return fallback;
      });
  }
  return voiceConfigPromise;
}

export async function initConversationVoice(): Promise<VoiceMode> {
  if (preferredMode) return preferredMode;
  if (preferredModeInit) return preferredModeInit;

  preferredModeInit = (async () => {
    await loadVoiceConfig();
    // Browser first — instant sync with on-screen text; server is fallback only.
    preferredMode = "browser";
    return preferredMode;
  })();

  return preferredModeInit;
}

export function resetConversationVoice(): void {
  preferredMode = null;
  preferredModeInit = null;
}

export function getConversationVoiceMode(): VoiceMode | null {
  return preferredMode;
}

export function isTtsSupported(): boolean {
  if (typeof window === "undefined") return false;
  return "speechSynthesis" in window || Boolean(voiceConfig?.gemini_tts_available);
}

function sanitizeForSpeech(text: string): string {
  return text
    .replace(/\[confirm-search\]/gi, "")
    .replace(/\[email-shortlist\]/gi, "")
    .replace(/₹\s*/g, "rupees ")
    .replace(/\bBHK\b/gi, "B H K")
    .replace(/\bPOI\b/g, "points of interest")
    .replace(/\bOSM\b/g, "Open Street Map")
    .replace(/[•·]/g, ", ")
    .replace(/[\[\](){}*_#]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function chunkText(text: string, maxChars: number): string[] {
  const clean = sanitizeForSpeech(text);
  if (!clean) return [];
  if (clean.length <= maxChars) return [clean];

  const sentences = clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) ?? [clean];
  const chunks: string[] = [];
  let buffer = "";

  const flush = () => {
    if (buffer.trim()) {
      chunks.push(buffer.trim());
      buffer = "";
    }
  };

  for (const sentence of sentences) {
    const part = sentence.trim();
    if (!part) continue;

    if (part.length > maxChars) {
      flush();
      for (const word of part.split(/\s+/)) {
        if (!word) continue;
        const next = buffer ? `${buffer} ${word}` : word;
        if (next.length > maxChars) {
          flush();
          buffer = word;
        } else {
          buffer = next;
        }
      }
      continue;
    }

    const next = buffer ? `${buffer} ${part}` : part;
    if (next.length > maxChars) {
      flush();
      buffer = part;
    } else {
      buffer = next;
    }
  }

  flush();
  return chunks.length ? chunks : [clean];
}

function resolveBrowserVoice(): SpeechSynthesisVoice | null {
  if (!("speechSynthesis" in window)) return null;
  if (lockedBrowserVoice?.voiceURI) {
    const stillThere = window.speechSynthesis
      .getVoices()
      .some((v) => v.voiceURI === lockedBrowserVoice?.voiceURI);
    if (stillThere) return lockedBrowserVoice;
    lockedBrowserVoice = null;
  }

  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  const ranked = [
    (v: SpeechSynthesisVoice) => v.lang.toLowerCase() === "en-in",
    (v: SpeechSynthesisVoice) =>
      /Samantha|Karen|Moira|Daniel|Google UK English Female|Google US English|Microsoft/i.test(
        v.name,
      ),
    (v: SpeechSynthesisVoice) => v.lang.toLowerCase().startsWith("en"),
    () => true,
  ];

  for (const score of ranked) {
    const match = voices.find(score);
    if (match) {
      lockedBrowserVoice = match;
      return match;
    }
  }

  return null;
}

if (typeof window !== "undefined" && "speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    lockedBrowserVoice = null;
    resolveBrowserVoice();
  };
}

function clearSynthKeepAlive(): void {
  if (synthKeepAliveTimer != null) {
    window.clearInterval(synthKeepAliveTimer);
    synthKeepAliveTimer = null;
  }
}

function startSynthKeepAlive(): void {
  clearSynthKeepAlive();
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  synthKeepAliveTimer = window.setInterval(() => {
    try {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.resume();
      }
    } catch {
      /* ignore */
    }
  }, SYNTH_KEEPALIVE_MS);
}

function releaseSharedAudio(): void {
  if (sharedAudio) {
    sharedAudio.pause();
    sharedAudio.onended = null;
    sharedAudio.onerror = null;
    try {
      sharedAudio.removeAttribute("src");
      sharedAudio.load();
    } catch {
      sharedAudio.src = "";
    }
  }
  if (sharedObjectUrl) {
    URL.revokeObjectURL(sharedObjectUrl);
    sharedObjectUrl = null;
  }
}

function speakBrowserChunk(text: string, generation: number): Promise<boolean> {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window) || generation !== activeGeneration) {
      resolve(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    const voice = resolveBrowserVoice();
    utterance.lang = voice?.lang || "en-US";
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;
    if (voice) utterance.voice = voice;

    let settled = false;
    let started = false;
    const finish = (ok: boolean) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(safety);
      resolve(ok);
    };

    utterance.onstart = () => {
      started = true;
    };
    utterance.onend = () => finish(true);
    utterance.onerror = () => finish(started);

    const safety = window.setTimeout(
      () => finish(started),
      Math.max(12_000, text.length * 90),
    );

    try {
      window.speechSynthesis.resume();
      window.speechSynthesis.speak(utterance);
    } catch {
      finish(false);
    }
  });
}

async function speakBrowser(text: string, generation: number): Promise<boolean> {
  if (!("speechSynthesis" in window) || generation !== activeGeneration) {
    return false;
  }

  const clean = sanitizeForSpeech(text);
  if (!clean) return false;

  const chunks = chunkText(clean, BROWSER_CHUNK_MAX_CHARS);
  speaking = true;
  startSynthKeepAlive();

  let played = false;
  try {
    for (const chunk of chunks) {
      if (generation !== activeGeneration) break;
      const ok = await speakBrowserChunk(chunk, generation);
      if (ok) played = true;
      else break;
    }
  } finally {
    clearSynthKeepAlive();
    if (generation === activeGeneration) speaking = false;
  }
  return played;
}

function ensureSharedAudio(): HTMLAudioElement {
  if (!sharedAudio) {
    sharedAudio = new Audio();
    sharedAudio.preload = "auto";
  }
  return sharedAudio;
}

async function playWavBlob(blob: Blob, generation: number): Promise<void> {
  if (generation !== activeGeneration) return;

  releaseSharedAudio();
  const audio = ensureSharedAudio();
  sharedObjectUrl = URL.createObjectURL(blob);
  audio.src = sharedObjectUrl;
  audio.volume = 1;
  speaking = true;

  try {
    await audio.play();
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => resolve();
      audio.onerror = () => reject(new Error("audio playback error"));
    });
  } finally {
    if (generation === activeGeneration) {
      releaseSharedAudio();
      speaking = false;
    }
  }
}

async function playBase64Wav(base64: string, generation: number): Promise<void> {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  await playWavBlob(new Blob([bytes], { type: "audio/wav" }), generation);
}

async function speakServerAudio(text: string, generation: number): Promise<boolean> {
  try {
    const blob = await fetchTtsAudio(text);
    if (generation !== activeGeneration) return false;
    if (blob.size < 100) return false;
    await playWavBlob(blob, generation);
    return true;
  } catch {
    return false;
  }
}

function isAudioActive(): boolean {
  if (speaking) return true;
  if (sharedAudio && !sharedAudio.paused) return true;
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    return (
      window.speechSynthesis.speaking || window.speechSynthesis.pending
    );
  }
  return false;
}

/** Browser speech with optional parallel server fetch if the engine stays silent. */
async function speakWithSyncFallback(
  text: string,
  generation: number,
): Promise<void> {
  if (!("speechSynthesis" in window)) {
    await speakServerAudio(text, generation);
    return;
  }

  let serverStarted = false;
  const serverFallback = window.setTimeout(() => {
    if (generation !== activeGeneration || serverStarted) return;
    const synth = window.speechSynthesis;
    if (synth.speaking || synth.pending) return;
    serverStarted = true;
    void speakServerAudio(text, generation);
  }, BROWSER_START_TIMEOUT_MS);

  const played = await speakBrowser(text, generation);
  window.clearTimeout(serverFallback);

  if (played || generation !== activeGeneration) return;
  if (!serverStarted) {
    await speakServerAudio(text, generation);
  }
}

export function stopSpeaking(): void {
  const wasActive = isAudioActive();
  activeGeneration += 1;
  speaking = false;

  if (pendingSpeakTimer != null) {
    window.clearTimeout(pendingSpeakTimer);
    pendingSpeakTimer = null;
  }

  clearSynthKeepAlive();

  if (wasActive) {
    releaseSharedAudio();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* ignore */
      }
    }
  }
}

function scheduleSpeak(generation: number, run: () => Promise<void>): void {
  if (pendingSpeakTimer != null) {
    window.clearTimeout(pendingSpeakTimer);
    pendingSpeakTimer = null;
  }
  const delay = isAudioActive() ? AFTER_CANCEL_MS : 0;
  const start = () => {
    if (generation !== activeGeneration) return;
    void run().catch(() => {});
  };
  if (delay === 0) {
    queueMicrotask(start);
    return;
  }
  pendingSpeakTimer = window.setTimeout(() => {
    pendingSpeakTimer = null;
    start();
  }, delay);
}

type SpeakOptions = {
  audioBase64?: string | null;
};

export function speakAssistantReply(
  assistantText: string,
  shortlistCount: number,
  options?: SpeakOptions,
): void {
  if (typeof window === "undefined") return;
  if (!getTtsEnabled()) return;

  const clean = sanitizeForSpeech(
    assistantTextForSpeech(assistantText, shortlistCount),
  );
  if (!clean && !options?.audioBase64) return;

  unlockSpeechAudio();
  stopSpeaking();
  const generation = activeGeneration;

  scheduleSpeak(generation, async () => {
    // Pre-generated WAV bundled with /turn — no extra network round trip.
    if (options?.audioBase64) {
      try {
        await playBase64Wav(options.audioBase64, generation);
        return;
      } catch {
        /* fall through to browser */
      }
    }

    if (!clean || generation !== activeGeneration) return;

    // Browser speech starts in sync with the on-screen reply.
    await speakWithSyncFallback(clean, generation);
  });
}

/** Immediate spoken status during a click gesture (e.g. Confirm Search). */
export function speakNow(text: string): void {
  if (typeof window === "undefined") return;
  if (!getTtsEnabled()) return;

  const clean = sanitizeForSpeech(text);
  if (!clean) return;

  unlockSpeechAudio();
  stopSpeaking();
  const generation = activeGeneration;

  scheduleSpeak(generation, async () => {
    if (generation !== activeGeneration) return;
    const played = await speakBrowser(clean, generation);
    if (!played && generation === activeGeneration) {
      await speakServerAudio(clean, generation);
    }
  });
}

export function speak(text: string): void {
  speakAssistantReply(text, 0);
}

export function isSpeaking(): boolean {
  if (speaking) return true;
  if (sharedAudio && !sharedAudio.paused) return true;
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    return window.speechSynthesis.speaking || window.speechSynthesis.pending;
  }
  return false;
}

/** @deprecated use speakAssistantReply */
export function speakSynced(
  turn: { assistant_text: string; shortlist?: { length: number } | null },
): void {
  speakAssistantReply(turn.assistant_text, turn.shortlist?.length ?? 0);
}

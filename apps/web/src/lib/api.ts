import type {
  SessionSnapshot,
  TurnResponse,
} from "@property-scout/schemas";

export type VoiceConfig = {
  gemini_tts_available: boolean;
  confidence_threshold: number;
  voice: string;
};

export type HealthResponse = {
  status: string;
  n8n_enabled?: boolean;
};

export type ExportResponse = {
  ok: boolean;
  message: string;
  delivered?: boolean;
};

/**
 * Resolve API base URL at call time (not module load).
 * - Local browser/dev: http://localhost:8000 (or NEXT_PUBLIC_API_URL)
 * - Any deployed host: same-origin /api-backend (server proxies via API_ORIGIN)
 */
function resolveApiUrl(): string {
  // Prefer explicit proxy flag (baked for Vercel builds).
  if (process.env.NEXT_PUBLIC_USE_API_PROXY === "1") {
    return "/api-backend";
  }

  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "").trim();
  const isLocalhostUrl =
    !configured ||
    configured.includes("localhost") ||
    configured.includes("127.0.0.1");

  // Browser on a real host must never call localhost.
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host !== "localhost" && host !== "127.0.0.1") {
      return "/api-backend";
    }
    return isLocalhostUrl ? configured || "http://localhost:8000" : configured;
  }

  // Server: Vercel always uses the proxy; local SSR may hit the API directly.
  if (process.env.VERCEL === "1") {
    return "/api-backend";
  }
  return configured || "http://localhost:8000";
}

function friendlyErrorMessage(status: number, detail: string): string {
  const trimmed = detail.trim();
  if (
    trimmed.startsWith("<!DOCTYPE") ||
    trimmed.startsWith("<html") ||
    trimmed.includes("This page could not be found")
  ) {
    return "API backend returned a web 404 page. Set API_ORIGIN to your FastAPI Vercel URL (apps/api), not the web URL, then redeploy.";
  }
  try {
    const parsed = JSON.parse(trimmed) as { detail?: string };
    if (parsed.detail) return parsed.detail;
  } catch {
    /* not JSON */
  }
  if (trimmed.length > 280) {
    return `API error HTTP ${status}. Check API_ORIGIN and that /health returns JSON.`;
  }
  return trimmed || `HTTP ${status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = resolveApiUrl();
  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new Error(
      apiUrl.startsWith("/")
        ? "Cannot reach the API proxy. Deploy apps/api, set API_ORIGIN on the web project to that URL, then redeploy."
        : `Cannot reach API at ${apiUrl}.`,
    );
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(friendlyErrorMessage(response.status, detail));
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    throw new Error(friendlyErrorMessage(response.status, text));
  }
  return response.json() as Promise<T>;
}

export function getApiUrl(): string {
  return resolveApiUrl();
}

export async function createSession(): Promise<SessionSnapshot> {
  return request<SessionSnapshot>("/session", { method: "POST" });
}

export async function getSession(sessionId: string): Promise<SessionSnapshot> {
  return request<SessionSnapshot>(`/session/${sessionId}`);
}

export async function postTurn(
  sessionId: string,
  text: string,
): Promise<TurnResponse> {
  return request<TurnResponse>(`/session/${sessionId}/turn`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function confirmSearch(sessionId: string): Promise<TurnResponse> {
  return request<TurnResponse>(`/session/${sessionId}/confirm-search`, {
    method: "POST",
  });
}

export async function selectListing(
  sessionId: string,
  listingId: string,
): Promise<SessionSnapshot> {
  return request<SessionSnapshot>(`/session/${sessionId}/select-listing`, {
    method: "POST",
    body: JSON.stringify({ listing_id: listingId }),
  });
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function checkHealth(): Promise<boolean> {
  try {
    const body = await fetchHealth();
    return body.status === "ok";
  } catch {
    return false;
  }
}

export async function fetchVoiceConfig(): Promise<VoiceConfig> {
  return request<VoiceConfig>("/voice/config");
}

export async function fetchTtsAudio(text: string): Promise<Blob> {
  const apiUrl = resolveApiUrl();
  const response = await fetch(`${apiUrl}/voice/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.blob();
}

export async function fetchSttTranscript(blob: Blob): Promise<string> {
  const apiUrl = resolveApiUrl();
  const form = new FormData();
  const extension = blob.type.includes("mp4")
    ? "mp4"
    : blob.type.includes("ogg")
      ? "ogg"
      : "webm";
  form.append("audio", blob, `speech.${extension}`);
  const response = await fetch(`${apiUrl}/voice/stt`, {
    method: "POST",
    body: form,
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `HTTP ${response.status}`);
  }
  const data = (await response.json()) as { text?: string };
  return (data.text ?? "").trim();
}

export async function exportShortlist(
  sessionId: string,
  email: string,
): Promise<ExportResponse> {
  return request<ExportResponse>(`/session/${sessionId}/export`, {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function fetchBookingSlots(
  sessionId: string,
  date: string,
): Promise<{ date: string; slots: string[] }> {
  const params = new URLSearchParams({ date });
  return request<{ date: string; slots: string[] }>(
    `/session/${sessionId}/booking/slots?${params.toString()}`,
  );
}

export async function createBooking(
  sessionId: string,
  listingId: string,
  date: string,
  slot: string,
): Promise<SessionSnapshot["booking"]> {
  return request<NonNullable<SessionSnapshot["booking"]>>(
    `/session/${sessionId}/bookings`,
    {
      method: "POST",
      body: JSON.stringify({
        listing_id: listingId,
        date,
        slot,
      }),
    },
  );
}

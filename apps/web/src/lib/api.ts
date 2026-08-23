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
 * Resolve API base URL.
 * - Local: http://localhost:8000
 * - Vercel: same-origin /api-backend proxy (avoids CORS + mixed-content localhost)
 * - Override: NEXT_PUBLIC_API_URL=https://your-api.vercel.app
 */
function resolveApiUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "").trim();
  if (configured && !configured.includes("localhost")) {
    return configured;
  }
  // On Vercel builds, never bake localhost into the client bundle.
  if (process.env.VERCEL === "1" || process.env.NEXT_PUBLIC_USE_API_PROXY === "1") {
    return "/api-backend";
  }
  if (configured) return configured;
  return "http://localhost:8000";
}

const API_URL = resolveApiUrl();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new Error(
      API_URL.startsWith("/")
        ? "Cannot reach the API proxy. Set API_ORIGIN on the web project to your FastAPI Vercel URL, then redeploy."
        : `Cannot reach API at ${API_URL}. Deploy the API and set NEXT_PUBLIC_API_URL / API_ORIGIN.`,
    );
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    let message = detail || `HTTP ${response.status}`;
    try {
      const parsed = JSON.parse(detail) as { detail?: string };
      if (parsed.detail) message = parsed.detail;
    } catch {
      /* keep raw */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function getApiUrl(): string {
  return API_URL;
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
  const response = await fetch(`${API_URL}/voice/tts`, {
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
  const form = new FormData();
  const extension = blob.type.includes("mp4")
    ? "mp4"
    : blob.type.includes("ogg")
      ? "ogg"
      : "webm";
  form.append("audio", blob, `speech.${extension}`);
  const response = await fetch(`${API_URL}/voice/stt`, {
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

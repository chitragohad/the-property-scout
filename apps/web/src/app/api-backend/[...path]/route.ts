import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function backendOrigin(req: NextRequest): string | null {
  const raw =
    process.env.API_ORIGIN?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "";
  if (!raw) return null;
  if (raw.startsWith("/")) return null;

  let origin: string;
  try {
    origin = new URL(raw).origin;
  } catch {
    return null;
  }

  // Common misconfig: pointing API_ORIGIN at the Next.js web URL.
  const webHost = req.nextUrl.hostname;
  const apiHost = new URL(origin).hostname;
  if (apiHost === webHost) {
    return null;
  }

  return origin;
}

function jsonError(detail: string, status: number): NextResponse {
  return NextResponse.json({ detail }, { status });
}

async function proxy(req: NextRequest, pathParts: string[]): Promise<NextResponse> {
  const origin = backendOrigin(req);
  if (!origin) {
    return jsonError(
      "API backend is not configured. Deploy the FastAPI project (Root Directory: apps/api), copy its URL, set API_ORIGIN on the web project to that URL (not the web URL), then redeploy.",
      503,
    );
  }

  const subpath = pathParts.map(encodeURIComponent).join("/");
  const target = `${origin}/${subpath}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", "application/json");

  let body: ArrayBuffer | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "upstream fetch failed";
    return jsonError(`Backend unreachable at ${origin}: ${message}`, 502);
  }

  const upstreamType = (upstream.headers.get("content-type") || "").toLowerCase();
  const raw = await upstream.arrayBuffer();
  const text = new TextDecoder().decode(raw.slice(0, 200));

  // Upstream returned a Next.js HTML 404 / error page — wrong API_ORIGIN.
  if (
    upstream.status === 404 ||
    upstreamType.includes("text/html") ||
    text.includes("<!DOCTYPE html") ||
    text.includes("This page could not be found")
  ) {
    return jsonError(
      `API_ORIGIN (${origin}) did not return the FastAPI backend. Open ${origin}/health in a browser — it must show {"status":"ok"}. If you see a Vercel/Next page, you used the web URL by mistake.`,
      502,
    );
  }

  const responseHeaders = new Headers();
  if (upstreamType) responseHeaders.set("content-type", upstreamType);
  responseHeaders.set("cache-control", "no-store");

  return new NextResponse(raw, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

type Ctx = { params: Promise<{ path?: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(req, path);
}

export async function PUT(req: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(req, path);
}

export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(req, path);
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(req, path);
}

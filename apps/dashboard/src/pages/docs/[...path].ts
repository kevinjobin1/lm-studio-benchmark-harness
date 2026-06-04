// Proxy /docs/* requests to the Starlight docs site.
// Primary: https://modellens-docs.pages.dev
// For local dev, override with DOCS_UPSTREAM=http://localhost:4321
import type { APIRoute } from "astro";

const DOCS_UPSTREAM = (
  (import.meta.env.DOCS_UPSTREAM as string) ||
  "https://modellens-docs.pages.dev"
).replace(/\/$/, "");

export const ALL: APIRoute = async ({ params, request }) => {
  const { path } = params;
  const upstreamUrl = `${DOCS_UPSTREAM}/${path || ""}`;

  const headers = new Headers(request.headers);
  headers.delete("host");

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: request.method !== "GET" && request.method !== "HEAD"
        ? request.body || undefined
        : undefined,
      redirect: "manual",
    });

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: upstream.headers,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return new Response(
      JSON.stringify({
        error: "Docs site temporarily unavailable",
        detail: message,
        upstream: upstreamUrl,
      }),
      {
        status: 502,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
};

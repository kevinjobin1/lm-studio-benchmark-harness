import type { APIRoute } from "astro";
import { loadTraceList } from "../../../lib/loadTraces";

/**
 * GET /api/traces
 *
 * Returns filtered list of trace index entries.
 *
 * Query params:
 *   model   — filter by model name (case-insensitive partial match)
 *   limit   — max entries to return (default: all)
 *   offset  — pagination offset (default: 0)
 *   status  — filter by status ("completed" | "failed")
 *
 * Response: TraceIndexEntry[]
 */
export const GET: APIRoute = async ({ request }) => {
  const url = new URL(request.url);
  const model = url.searchParams.get("model") || undefined;
  const limit = url.searchParams.has("limit")
    ? parseInt(url.searchParams.get("limit")!, 10)
    : undefined;
  const offset = url.searchParams.has("offset")
    ? parseInt(url.searchParams.get("offset")!, 10)
    : undefined;
  const status = (url.searchParams.get("status") as
    | "completed"
    | "failed"
    | null) || undefined;

  const entries = await loadTraceList({ model, limit, offset, status });

  return new Response(JSON.stringify(entries), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

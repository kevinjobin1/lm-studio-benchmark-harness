import type { APIRoute } from "astro";
import { loadTraceList } from "../../../lib/loadTraces";

/**
 * GET /api/traces
 *
 * Returns filtered list of trace index entries.
 *
 * In SSR mode: tries SQLite (``results/runs.db``) first via
 * ``loadTraceEntriesFromDb()``. Falls back to the flat JSON
 * trace index if SQLite is unavailable (Cloudflare Workers).
 *
 * Query params:
 *   model   — filter by model name (case-insensitive partial match)
 *   limit   — max entries to return (default: 50)
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

  // Try SQLite first in SSR mode (local dev / Node.js)
  if (import.meta.env.SSR) {
    try {
      const { loadTraceEntriesFromDb } = await import("../../../lib/loadResultsDb");
      const dbResults = loadTraceEntriesFromDb(model, limit ?? 50, offset ?? 0);
      if (dbResults && dbResults.length > 0) {
        return new Response(JSON.stringify(dbResults), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
    } catch {
      // better-sqlite3 not available — fall through to JSON
    }
  }

  // Fall back to flat JSON trace index
  const entries = await loadTraceList({ model, limit, offset, status });

  return new Response(JSON.stringify(entries), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

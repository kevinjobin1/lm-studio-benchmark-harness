import type { APIRoute } from "astro";
import { loadReplayManifest } from "../../../lib/loadReplays";

/**
 * GET /api/replays
 *
 * Returns the list of all recorded replay sessions (index entries).
 *
 * Query params:
 *   model   — filter by model name (case-insensitive partial match)
 *   limit   — max entries to return (default: all)
 *   offset  — pagination offset (default: 0)
 *
 * Response: ReplayIndexEntry[]
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

  const manifest = await loadReplayManifest();
  let entries = [...manifest.replays];

  // Filter by model
  if (model) {
    const lower = model.toLowerCase();
    entries = entries.filter((e) => e.model.toLowerCase().includes(lower));
  }

  // Sort by started_at descending (most recent first)
  entries.sort(
    (a, b) =>
      new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
  );

  // Paginate
  const off = offset ?? 0;
  const lim = limit ?? entries.length;
  entries = entries.slice(off, off + lim);

  return new Response(JSON.stringify(entries), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

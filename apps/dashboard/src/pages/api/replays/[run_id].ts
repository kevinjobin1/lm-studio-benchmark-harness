import type { APIRoute } from "astro";
import { loadReplay } from "../../../lib/loadReplays";

/**
 * GET /api/replays/[run_id]
 *
 * Returns the full replay data for a single session by its run_id.
 *
 * Response: ReplayData | { error: string } (404 if not found)
 */
export const GET: APIRoute = async ({ params }) => {
  const { run_id } = params;

  if (!run_id) {
    return new Response(
      JSON.stringify({ error: "Missing run_id" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const replay = await loadReplay(decodeURIComponent(run_id));

  if (!replay) {
    return new Response(
      JSON.stringify({ error: `Replay not found: ${run_id}` }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(JSON.stringify(replay), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

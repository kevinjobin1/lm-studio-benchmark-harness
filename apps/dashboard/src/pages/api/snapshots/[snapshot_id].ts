import type { APIRoute } from "astro";
import { loadSnapshot } from "../../../lib/loadSnapshots";

/**
 * GET /api/snapshots/[snapshot_id]
 *
 * Returns a single snapshot by its snapshot_id.
 *
 * Response: SnapshotData | { error: string } (404 if not found)
 */
export const GET: APIRoute = async ({ params }) => {
  const { snapshot_id } = params;

  if (!snapshot_id) {
    return new Response(
      JSON.stringify({ error: "Missing snapshot_id" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const snapshot = await loadSnapshot(decodeURIComponent(snapshot_id));

  if (!snapshot) {
    return new Response(
      JSON.stringify({ error: `Snapshot not found: ${snapshot_id}` }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(JSON.stringify(snapshot), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

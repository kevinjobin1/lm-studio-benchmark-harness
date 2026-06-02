import type { APIRoute } from "astro";
import { loadSnapshotManifest, saveSnapshot } from "../../../lib/loadSnapshots";
import type { SnapshotData } from "../../../lib/loadSnapshots";

/**
 * GET /api/snapshots
 *
 * Returns the list of all saved snapshots (index entries).
 *
 * Response: SnapshotIndexEntry[]
 */
export const GET: APIRoute = async () => {
  const manifest = await loadSnapshotManifest();
  return new Response(JSON.stringify(manifest.snapshots), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

/**
 * POST /api/snapshots
 *
 * Save a new snapshot from a TraceRun.
 *
 * Body: SnapshotData (full snapshot payload)
 * Response: { snapshot_id: string, url: string }
 */
export const POST: APIRoute = async ({ request }) => {
  try {
    const snapshot: SnapshotData = await request.json();

    if (!snapshot.snapshot_id || !snapshot.model || !snapshot.trace) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: snapshot_id, model, trace" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    const result = await saveSnapshot(snapshot);
    return new Response(JSON.stringify(result), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: `Failed to save snapshot: ${(err as Error).message}` }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
};

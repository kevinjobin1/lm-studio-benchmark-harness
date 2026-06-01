/**
 * GET /api/run-benchmark/active
 * Returns lightweight status — whether any benchmark process is currently running.
 */

import type { APIRoute } from "astro";
import { getAll } from "../../../lib/processRegistry";

export const GET: APIRoute = async () => {
  const all = getAll();
  const running = all.filter((e) => e.status === "running");

  return new Response(
    JSON.stringify({
      active: running.length > 0,
      processes: running.map((e) => ({
        pid: e.pid,
        model: e.model,
        quick: e.quick,
        startTime: e.startTime,
      })),
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
};

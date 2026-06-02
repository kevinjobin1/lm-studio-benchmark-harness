import type { APIRoute } from "astro";
import { getAll } from "../../../lib/processRegistry";

export const GET: APIRoute = async () => {
  const all = getAll();
  const running = all.filter((p) => p.status === "running");

  return new Response(
    JSON.stringify({
      active: running.length > 0,
      processes: running.map((p) => ({
        pid: p.pid,
        model: p.model,
        quick: p.quick,
        startTime: p.startTime,
      })),
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

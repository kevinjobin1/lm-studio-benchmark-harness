/**
 * POST /api/run-benchmark/kill?pid=<pid>
 * Kills a running benchmark process by PID.
 */

import type { APIRoute } from "astro";
import { killProcess, getByPid } from "../../../lib/processRegistry";

export const POST: APIRoute = async ({ url }) => {
  const pidParam = url.searchParams.get("pid");

  if (!pidParam) {
    return new Response(
      JSON.stringify({ error: "Missing pid parameter. Use ?pid=<number>" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const pid = parseInt(pidParam, 10);
  if (isNaN(pid)) {
    return new Response(
      JSON.stringify({ error: "Invalid pid parameter" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const entry = getByPid(pid);
  if (!entry) {
    return new Response(
      JSON.stringify({ error: `No process found with pid ${pid}` }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  }

  if (entry.status !== "running") {
    return new Response(
      JSON.stringify({
        success: false,
        message: `Process ${pid} is already ${entry.status}`,
        pid,
        status: entry.status,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }

  const killed = killProcess(pid);
  if (killed) {
    return new Response(
      JSON.stringify({
        success: true,
        message: `Sent SIGTERM to process ${pid} (${entry.model})`,
        pid,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(
    JSON.stringify({
      success: false,
      message: `Failed to kill process ${pid}`,
      pid,
    }),
    { status: 500, headers: { "Content-Type": "application/json" } },
  );
};

import type { APIRoute } from "astro";
import { getByPid } from "../../../lib/processRegistry";

export const GET: APIRoute = async ({ url }) => {
  const pidStr = url.searchParams.get("pid");
  if (!pidStr) {
    return new Response(JSON.stringify({ error: "Missing pid parameter" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const pid = Number(pidStr);
  if (isNaN(pid)) {
    return new Response(JSON.stringify({ error: "Invalid pid" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const entry = getByPid(pid);
  if (!entry) {
    return new Response(JSON.stringify({ error: "Process not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(
    JSON.stringify({
      pid: entry.pid,
      status: entry.status,
      stdout: entry.stdout,
      stderr: entry.stderr,
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

import type { APIRoute } from "astro";
import { killProcess } from "../../../lib/processRegistry";

export const POST: APIRoute = async ({ url }) => {
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

  const killed = killProcess(pid);
  return new Response(
    JSON.stringify({ success: killed, pid }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

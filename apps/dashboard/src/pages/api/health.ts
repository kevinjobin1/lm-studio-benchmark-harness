import type { APIRoute } from "astro";

const START_TIME = Date.now();

export const GET: APIRoute = async () => {
  const uptime = Math.floor((Date.now() - START_TIME) / 1000);
  const mins = Math.floor(uptime / 60);
  const secs = uptime % 60;

  return new Response(
    JSON.stringify({
      status: "ok",
      uptime: `${mins}m ${secs}s`,
      uptime_seconds: uptime,
      started_at: new Date(START_TIME).toISOString(),
      timestamp: new Date().toISOString(),
      version: "1.0.0",
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

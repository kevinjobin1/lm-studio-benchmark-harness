import type { APIRoute } from "astro";
import { getAll } from "../../../lib/processRegistry";

/**
 * GET /api/events/health — Returns whether the SSE bridge is currently
 * connected and serving events.
 *
 * The SSE bridge is a Python HTTP server spawned by the benchmark
 * subprocess.  This endpoint checks the process registry for any running
 * benchmark with an ssePort, then probes that port to confirm the bridge
 * is responsive.
 *
 * Response:
 *   {
 *     connected: boolean,    // true if a bridge is reachable
 *     port: number | null,   // the bridge port (null if no process)
 *     model: string | null,  // model name of the active benchmark
 *     provider: string | null,
 *     timestamp: string      // ISO 8601
 *   }
 */
export const GET: APIRoute = async () => {
  const defaultPort = parseInt(
    typeof process !== "undefined" && process.env?.MODELLENS_SSE_PORT
      ? process.env.MODELLENS_SSE_PORT
      : "9090",
    10,
  );

  // ── Find a running process with an SSE bridge ──────────────
  let ssePort: number | null = null;
  let model: string | null = null;
  let provider: string | null = null;

  try {
    const running = getAll().filter((p) => p.status === "running");
    for (const proc of running) {
      if (proc.ssePort) {
        ssePort = proc.ssePort;
        model = proc.model;
        provider = proc.provider;
        break;
      }
    }
  } catch {
    // process registry unavailable
  }

  // If no active process was found, fall back to the default port
  if (ssePort === null) {
    ssePort = defaultPort;
  }

  // ── Probe the SSE bridge ───────────────────────────────────
  let connected = false;

  if (ssePort) {
    try {
      const abortController = new AbortController();
      const timeout = setTimeout(() => abortController.abort(), 2000);

      const response = await fetch(`http://127.0.0.1:${ssePort}/events`, {
        method: "GET",
        signal: abortController.signal,
      });
      clearTimeout(timeout);

      connected = response.ok;
    } catch {
      // Bridge not reachable
      connected = false;
    }
  }

  return new Response(
    JSON.stringify({
      connected,
      port: ssePort,
      model,
      provider,
      timestamp: new Date().toISOString(),
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

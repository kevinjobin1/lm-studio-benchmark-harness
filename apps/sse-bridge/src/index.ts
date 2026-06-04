/**
 * Model Lens SSE Bridge Worker
 *
 * Dedicated Cloudflare Worker with Durable Objects for real-time
 * Server-Sent Events streaming between the Python benchmark and
 * dashboard browser clients.
 *
 * Routes:
 *   POST /events     — Python benchmark publishes events here
 *   GET  /events     — Dashboard connects for SSE stream
 *   GET  /health     — Health check
 *   GET  /            — Info page
 *
 * Architecture (per Cloudflare best practices):
 *   - DurableObject for stateful SSE connection management
 *   - SQLite for event buffering
 *   - Alarm-based keepalive for dead connection cleanup
 *   - Deterministic routing via getByName("default")
 */

import { HEALTH_OK } from "./types";

export { SSEBridgeDO } from "./SSEBridgeDO";

/** Workers environment with DO binding. */
interface Env {
  SSE_BRIDGE: DurableObjectNamespace<import("./SSEBridgeDO").SSEBridgeDO>;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    // Route to Durable Object for /events and /health
    if (
      url.pathname === "/events" ||
      url.pathname === "/health"
    ) {
      const id = env.SSE_BRIDGE.idFromName("default");
      const stub = env.SSE_BRIDGE.get(id);
      return stub.fetch(request);
    }

    // Info page
    if (url.pathname === "/" || url.pathname === "") {
      return new Response(
        JSON.stringify({
          service: "modellens-sse-bridge",
          version: "0.1.0",
          endpoints: {
            "POST /events": "Publish benchmark events",
            "GET /events": "SSE stream for dashboard clients",
            "GET /health": "Health check and connection count",
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    return new Response("Not found", { status: 404 });
  },
};

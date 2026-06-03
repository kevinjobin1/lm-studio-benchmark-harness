// @vitest-environment node
/**
 * Integration test for GET /api/events — real HTTP server as the SSE bridge,
 * Astro handler proxying, and EventSource client consuming the stream.
 *
 * This validates the full stack end-to-end: bridge → proxy → EventSource,
 * with real HTTP, fetch(), and SSE protocol parsing.
 */
import http from "node:http";
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import { EventSource } from "eventsource";

// Hoisted mock — Vitest's static analysis moves this to the top of the file
// so it applies to any dynamic import of ./index after vi.resetModules().
vi.mock("../../../lib/processRegistry", () => ({
  getAll: () => [],
}));

describe("GET /api/events — integration", () => {
  let bridgeServer: http.Server;
  let proxyServer: http.Server;
  let proxyPort: number;
  let GET: any;

  beforeAll(async () => {
    // ── 1. Start the real SSE bridge server ─────────────────────
    bridgeServer = http.createServer((req, res) => {
      if (req.url === "/events" && req.method === "GET") {
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
        });
        // Send one MetricEvent then close
        res.write(
          'event: MetricEvent\ndata: {"name":"score","value":0.95}\n\n',
        );
        res.end();
      } else {
        res.writeHead(404);
        res.end();
      }
    });
    await new Promise<void>((resolve) => bridgeServer.listen(0, resolve));
    const bridgePort = (bridgeServer.address() as any).port;

    // ── 2. Point the Astro handler at our bridge ────────────────
    process.env.MODELLENS_SSE_PORT = String(bridgePort);
    process.env.MODELLENS_SSE_RETRY_MS = "50";

    // Clear module cache so the handler picks up the fresh env vars
    // (the hoisted vi.mock will still apply after reset)
    vi.resetModules();
    const mod = await import("./index");
    GET = mod.GET;

    // ── 3. Start the proxy server wrapping the Astro handler ────
    proxyServer = http.createServer(async (_req, res) => {
      try {
        const response = await GET({} as any);
        res.writeHead(response.status, Object.fromEntries(response.headers));

        const reader = response.body!.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            res.end();
            break;
          }
          res.write(value);
        }
      } catch (err) {
        res.writeHead(500);
        res.end(String(err));
      }
    });
    await new Promise<void>((resolve) => proxyServer.listen(0, resolve));
    proxyPort = (proxyServer.address() as any).port;
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => proxyServer?.close(() => resolve()));
    await new Promise<void>((resolve) => bridgeServer?.close(() => resolve()));
    delete process.env.MODELLENS_SSE_PORT;
    delete process.env.MODELLENS_SSE_RETRY_MS;
  });

  it("receives a MetricEvent from the bridge through the proxy via EventSource", async () => {
    const metricEvents: string[] = [];
    let receivedConnected = false;

    const es = new EventSource(`http://127.0.0.1:${proxyPort}/`);

    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error("Timed out waiting for MetricEvent")),
        5000,
      );

      es.addEventListener("_status", (e: any) => {
        const data = JSON.parse(e.data as string);
        if (data.connected === true) {
          receivedConnected = true;
        }
      });

      es.addEventListener("MetricEvent", (e: any) => {
        metricEvents.push(e.data as string);
        clearTimeout(timeout);
        es.close();
        resolve();
      });

      es.onerror = () => {
        // EventSource fires error on connection close — ignore if already resolved
      };
    });

    expect(receivedConnected).toBe(true);
    expect(metricEvents).toHaveLength(1);
    const parsed = JSON.parse(metricEvents[0]);
    expect(parsed.name).toBe("score");
    expect(parsed.value).toBe(0.95);
  }, 10000);
});

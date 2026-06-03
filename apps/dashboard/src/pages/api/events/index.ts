import type { APIRoute } from "astro";
import { getAll } from "../../../lib/processRegistry";

/**
 * GET /api/events — Server-Sent Events endpoint for real-time benchmark updates.
 *
 * Proxies events from the Python SSE bridge (running inside the benchmark
 * subprocess) to browser clients.  If no benchmark is running or the SSE
 * bridge is unreachable, sends periodic status events so the client's
 * EventSource can auto-reconnect when a new benchmark starts.
 */
export const GET: APIRoute = async () => {
  const encoder = new TextEncoder();

  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();



  // Determine the SSE port.  Try to find it from a running benchmark process
  // first, otherwise fall back to the default port (9090 or env var).
  const defaultPort = parseInt(
    typeof process !== "undefined" && process.env?.MODELLENS_SSE_PORT
      ? process.env.MODELLENS_SSE_PORT
      : "9090",
    10,
  );

  let ssePort = defaultPort;

  // Retry interval — how long to wait between bridge connection attempts.
  // Configurable via MODELLENS_SSE_RETRY_MS env var (default 3000ms).
  // Tests set this to a short value (e.g. 50ms) for fast execution.
  const retryIntervalMs = parseInt(
    typeof process !== "undefined" && process.env?.MODELLENS_SSE_RETRY_MS
      ? process.env.MODELLENS_SSE_RETRY_MS
      : "3000",
    10,
  );

  let streamClosed = false;

  const send = (event: string, data: Record<string, unknown>) => {
    if (streamClosed) return Promise.resolve();
    const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    return writer.write(encoder.encode(msg)).catch((err) => {
      streamClosed = true;
      throw err;
    });
  };

  // Kick off the SSE proxy in the background
  const startProxy = async () => {
    // Try to find the port from an active process
    try {
      const running = getAll().filter((p) => p.status === "running");
      for (const proc of running) {
        if (proc.ssePort) {
          ssePort = proc.ssePort;
          break;
        }
      }
    } catch {
      // process registry query failed — use default port
    }

    // Send initial status
    await send("_status", { connected: false, port: ssePort });

    // Keep trying to connect to the Python SSE bridge
    // Once connected, pipe events directly to the client
    while (true) {
      try {
        const abortController = new AbortController();
        // Timeout the connection attempt
        const timeout = setTimeout(() => abortController.abort(), retryIntervalMs);

        const response = await fetch(
          `http://127.0.0.1:${ssePort}/events`,
          { signal: abortController.signal },
        );
        clearTimeout(timeout);

        if (!response.ok || !response.body) {
          throw new Error(`SSE server returned ${response.status}`);
        }

        // Connected!  Tell the client and start piping.
        await send("_status", { connected: true, port: ssePort });

        const reader = response.body.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          await writer.write(value);
        }

        // If the stream ended cleanly, the benchmark finished
        await send("_status", { connected: false, message: "Benchmark finished" });
        break;
      } catch (err) {
        // If the client disconnected, stop retrying
        if (streamClosed) {
          break;
        }

        // SSE bridge not reachable yet — wait and retry
        const message = err instanceof Error ? err.message : "Unknown error";
        await send("_status", {
          connected: false,
          error: message,
          retrying: true,
        });

        // Wait before reconnecting
        await new Promise((resolve) => setTimeout(resolve, retryIntervalMs));
      }
    }

    // Close the stream when the benchmark is done
    try {
      await writer.close();
    } catch {
      // Client may have already disconnected
    }
  };

  // Start the proxy in the background (don't await — the response needs
  // to return immediately with the stream)
  startProxy().catch(() => {
    writer.close().catch(() => {});
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "Access-Control-Allow-Origin": "*",
    },
  });
};

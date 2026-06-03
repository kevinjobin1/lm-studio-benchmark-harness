import type { APIRoute } from "astro";
import { getAll } from "../../../lib/processRegistry";

/**
 * GET /api/events/bridge-status — Detailed diagnostics about the SSE bridge
 * and its associated benchmark process.
 *
 * Returns richer information than the simple /api/events/health endpoint,
 * including probe latency, process metadata, and bridge configuration.
 *
 * Response:
 *   {
 *     connected: boolean,       // true if a bridge is reachable
 *     port: number | null,      // detected bridge port
 *     latency_ms: number | null,// probe response time (ms)
 *     process: {
 *       pid: number | null,
 *       model: string | null,
 *       provider: string | null,
 *       started_at: string | null,
 *       status: string | null,
 *       uptime_seconds: number | null,
 *       stdout_bytes: number | null,
 *       stderr_bytes: number | null
 *     },
 *     bridge: {
 *       default_port: number,
 *       probe_url: string | null,
 *       probe_success: boolean,
 *       last_error: string | null
 *     },
 *     timestamp: string         // ISO 8601
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
  let processPid: number | null = null;
  let model: string | null = null;
  let provider: string | null = null;
  let startedAt: string | null = null;
  let procStatus: string | null = null;
  let stdoutBytes: number | null = null;
  let stderrBytes: number | null = null;
  let uptimeSeconds: number | null = null;

  try {
    const running = getAll().filter((p) => p.status === "running");
    for (const proc of running) {
      if (proc.ssePort) {
        ssePort = proc.ssePort;
        processPid = proc.pid;
        model = proc.model;
        provider = proc.provider;
        startedAt = proc.startTime;
        procStatus = proc.status;
        stdoutBytes = (proc.stdout?.length) ?? null;
        stderrBytes = (proc.stderr?.length) ?? null;
        if (proc.startTime) {
          uptimeSeconds = Math.floor(
            (Date.now() - new Date(proc.startTime).getTime()) / 1000,
          );
        }
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

  // ── Probe the SSE bridge with latency measurement ──────────
  let connected = false;
  let latencyMs: number | null = null;
  let lastError: string | null = null;
  let probeSuccess = false;

  if (ssePort) {
    const probeUrl = `http://127.0.0.1:${ssePort}/events`;
    const probeStart = Date.now();

    try {
      const abortController = new AbortController();
      const timeout = setTimeout(() => abortController.abort(), 2000);

      const response = await fetch(probeUrl, {
        method: "GET",
        signal: abortController.signal,
      });
      clearTimeout(timeout);

      latencyMs = Date.now() - probeStart;
      connected = response.ok;
      probeSuccess = true;
    } catch (err) {
      latencyMs = Date.now() - probeStart;
      connected = false;
      probeSuccess = false;
      lastError = err instanceof Error ? err.message : "Unknown error";
    }
  }

  return new Response(
    JSON.stringify({
      connected,
      port: ssePort,
      latency_ms: latencyMs,
      process: {
        pid: processPid,
        model,
        provider,
        started_at: startedAt,
        status: procStatus,
        uptime_seconds: uptimeSeconds,
        stdout_bytes: stdoutBytes,
        stderr_bytes: stderrBytes,
      },
      bridge: {
        default_port: defaultPort,
        probe_url: ssePort ? `http://127.0.0.1:${ssePort}/events` : null,
        probe_success: probeSuccess,
        last_error: lastError,
      },
      timestamp: new Date().toISOString(),
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

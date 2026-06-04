/**
 * SSEBridgeDO — Durable Object managing real-time SSE connections.
 *
 * Architecture:
 *   Python benchmark → POST /events → SSEBridgeDO → broadcast → SSE clients (dashboard)
 *
 * Each DO instance holds a set of active SSE connection writers.
 * Events published via POST /events are broadcast to all connections.
 * A periodic alarm sends keepalives and cleans up dead connections.
 *
 * Per Cloudflare Durable Objects best practices:
 *   - Uses SQLite storage for event buffering (schema init in constructor)
 *   - blockConcurrencyWhile() only for initialization
 *   - Alarm for periodic keepalive, not for every request
 *   - Deterministic routing via getByName("default")
 */

import { DurableObject } from "cloudflare:workers";
import { formatSSEMessage, KEEPALIVE, encoder, type IncomingEvent } from "./types";

/** DO environment bindings (no additional bindings needed). */
export interface SSEBridgeEnv {
  SSE_BRIDGE: DurableObjectNamespace<SSEBridgeDO>;
}



/** An active SSE connection (client waiting for events). */
interface SSEConnection {
  writer: WritableStreamDefaultWriter<Uint8Array>;
  connectedAt: number;
}

export class SSEBridgeDO extends DurableObject<SSEBridgeEnv> {
  /** Active SSE connections keyed by connection ID. */
  private connections: Map<string, SSEConnection> = new Map();

  /** SQL storage handle for event buffering. */
  private sql: SqlStorage;

  constructor(ctx: DurableObjectState, env: SSEBridgeEnv) {
    super(ctx, env);
    this.sql = ctx.storage.sql;

    // Initialize schema once, using blockConcurrencyWhile per DO best practices
    ctx.blockConcurrencyWhile(async () => {
      this.sql.exec(`
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_type TEXT NOT NULL,
          data TEXT NOT NULL,
          created_at INTEGER NOT NULL DEFAULT (unixepoch() * 1000)
        )
      `);
      this.sql.exec(`
        CREATE INDEX IF NOT EXISTS idx_events_type
        ON events(event_type)
      `);
    });
  }

  // ── HTTP Handler ────────────────────────────────────────────

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method;

    // POST /events — Python benchmark publishes an event
    if (method === "POST" && url.pathname === "/events") {
      return this.handlePostEvent(request);
    }

    // GET /events — Dashboard connects for SSE stream
    if (method === "GET" && url.pathname === "/events") {
      return this.handleSSEConnection();
    }

    // GET /health — Health check
    if (url.pathname === "/health") {
      return this.handleHealth();
    }

    return new Response("Not found", { status: 404 });
  }

  // ── POST /events — Receive event from Python benchmark ──────

  private async handlePostEvent(request: Request): Promise<Response> {
    let event: IncomingEvent;
    try {
      event = (await request.json()) as IncomingEvent;
    } catch {
      return new Response("Invalid JSON", { status: 400 });
    }

    // Buffer the event in SQLite for replay/debugging
    this.sql.exec(
      "INSERT INTO events (event_type, data) VALUES (?, ?)",
      event._event_type ?? "unknown",
      JSON.stringify(event),
    );

    // Trim old events (keep last 10,000)
    const count = (this.sql.exec("SELECT COUNT(*) as c FROM events").one() as { c: number }).c;
    if (count > 10_000) {
      this.sql.exec(
        "DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 10000)",
      );
    }

    // Broadcast to all connected SSE clients
    const message = encoder.encode(formatSSEMessage(event));
    const deadConnections: string[] = [];

    for (const [id, conn] of this.connections) {
      try {
        await conn.writer.write(message);
      } catch {
        deadConnections.push(id);
      }
    }

    // Clean up dead connections
    for (const id of deadConnections) {
      try {
        this.connections.get(id)?.writer.close();
      } catch { /* already closed */ }
      this.connections.delete(id);
    }

    return new Response(JSON.stringify({
      ok: true,
      broadcasted: this.connections.size,
      dead: deadConnections.length,
    }), {
      status: 202,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });
  }

  // ── GET /events — Dashboard connects for SSE stream ─────────

  private async handleSSEConnection(): Promise<Response> {
    const connectionId = crypto.randomUUID();
    const connections = this.connections;
    let writer: WritableStreamDefaultWriter<Uint8Array> | null = null;

    // Use a ReadableStream backed by a WritableStream so data enqueued
    // via the writer reaches the HTTP response.  TransformStream does
    // not reliably pipe pre-Response writes in the workerd runtime.
    const readable = new ReadableStream<Uint8Array>({
      start(controller) {
        const ws = new WritableStream<Uint8Array>({
          write(chunk) {
            controller.enqueue(chunk);
          },
          close() {
            // SSE connections stay open indefinitely — never close
          },
        });
        writer = ws.getWriter();

        connections.set(connectionId, {
          writer: writer!,
          connectedAt: Date.now(),
        });

        // Send the _connected event immediately (fire-and-forget —
        // errors are handled by the catch callback).
        writer!.write(
          encoder.encode(
            formatSSEMessage({
              _event_type: "_connected",
              connection_id: connectionId,
              service: "modellens-sse-bridge",
              timestamp: Date.now(),
            }),
          ),
        ).catch(() => {
          connections.delete(connectionId);
        });
      },
      cancel() {
        if (writer) {
          writer.close().catch(() => {});
        }
        connections.delete(connectionId);
      },
    });

    // Ensure alarm is set for keepalive
    const currentAlarm = await this.ctx.storage.getAlarm();
    if (currentAlarm === null) {
      await this.ctx.storage.setAlarm(Date.now() + 30_000);
    }

    return new Response(readable, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
      },
    });
  }

  // ── GET /health ─────────────────────────────────────────────

  private async handleHealth(): Promise<Response> {
    return new Response(
      JSON.stringify({
        status: "ok",
        connections: this.connections.size,
        service: "modellens-sse-bridge",
      }),
      {
        headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      },
    );
  }

  // ── Alarm — Periodic keepalive and dead connection cleanup ──

  async alarm(): Promise<void> {
    const deadConnections: string[] = [];

    for (const [id, conn] of this.connections) {
      try {
        await conn.writer.write(KEEPALIVE);
      } catch {
        deadConnections.push(id);
      }
    }

    for (const id of deadConnections) {
      try {
        this.connections.get(id)?.writer.close();
      } catch { /* already closed */ }
      this.connections.delete(id);
    }

    // Reschedule alarm if there are still active connections
    if (this.connections.size > 0) {
      await this.ctx.storage.setAlarm(Date.now() + 30_000);
    }
  }
}

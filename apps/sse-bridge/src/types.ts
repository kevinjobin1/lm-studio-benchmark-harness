/**
 * Shared types for the Model Lens SSE Bridge Worker.
 *
 * Mirrors the Python EventBus event taxonomy from packages/events/__init__.py.
 * The Python benchmark POSTs events to this Worker, which broadcasts them
 * to connected SSE clients (dashboard browsers).
 */

/** Incoming event from the Python benchmark (POST /events). */
export interface IncomingEvent {
  _event_type: string;
  timestamp?: number;
  id?: string;
  model?: string;
  run_id?: string;
  source?: string;
  provider?: string;
  [key: string]: unknown;
}

/** SSE wire format: `data: <JSON>\n\n` */
export function formatSSEMessage(data: IncomingEvent): string {
  return `data: ${JSON.stringify(data)}\n\n`;
}

/** Encoder for streaming SSE messages. */
export const encoder = new TextEncoder();

/** SSE keepalive comment (prevents connection timeout). */
export const KEEPALIVE = encoder.encode(": keepalive\n\n");

/** Health check response. */
export const HEALTH_OK = {
  status: "ok",
  service: "modellens-sse-bridge",
  architecture: "Worker + DurableObject",
};

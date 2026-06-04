/**
 * useEventStream — React hook for consuming real-time benchmark events
 * via Server-Sent Events from the dashboard's /api/events endpoint.
 *
 * The Python SSE bridge sends all events as *unnamed* SSE messages
 * (no ``event:`` line), so the browser's ``EventSource.onmessage``
 * receives everything. The event type is embedded in the data as
 * ``_event_type``.
 *
 * Usage:
 *   const { connected, events, clearEvents, getEventsByType } = useEventStream();
 *
 *   // Filter by event type
 *   const tokens = events.filter(e => e._event_type === 'TokenGeneratedEvent');
 *   const metrics = events.filter(e => e._event_type === 'MetricEvent');
 *   const lifecycle = events.filter(e => e._event_type === 'RunLifecycleEvent');
 */

import { useEffect, useRef, useState, useCallback } from "react";

// ── Types ─────────────────────────────────────────────────────────

export interface SSEEvent {
  /** Event type discriminator (e.g. "TokenGeneratedEvent", "_status"). */
  _event_type: string;
  /** Timestamp in milliseconds since epoch. */
  timestamp?: number;
  /** Unique event ID. */
  id?: string;
  /** Model name associated with the event (if applicable). */
  model?: string;
  /** Benchmark run ID. */
  run_id?: string;
  /** Source component that emitted the event. */
  source?: string;
  /** Provider name (e.g. "lm-studio", "ollama"). */
  provider?: string;
  // Additional event-type-specific fields
  [key: string]: unknown;
}

export interface EventStreamState {
  /** Whether the SSE bridge is currently connected. */
  connected: boolean;
  /** All received events (most recent at the end, limited to 5000). */
  events: SSEEvent[];
  /** Number of events received. */
  eventCount: number;
  /** Clear the event buffer. */
  clearEvents: () => void;
  /** Get events filtered by ``_event_type``. */
  getEventsByType: (type: string) => SSEEvent[];
  /** Latest event of each ``_event_type``. */
  latestByType: Record<string, SSEEvent | undefined>;
}

// ── Hook ──────────────────────────────────────────────────────────

const MAX_BUFFERED_EVENTS = 5000;

/** Cloudflare Worker SSE Bridge (production / remote access). */
const SSE_WORKER_URL =
  import.meta.env.PUBLIC_SSE_WORKER_URL ||
  "https://modellens-sse-bridge.kevin-jobin-1.workers.dev";

/** Local SSE relay (preferred for low-latency local dev). */
const LOCAL_SSE_URL = "http://localhost:9090";

/**
 * Resolve the best SSE endpoint for the current environment.
 *
 * Tries to reach the local SSE relay (``modellens sse serve``) first.
 * If reachable, uses it for sub-millisecond event latency.  Falls back
 * to the Cloudflare Worker SSE Bridge for remote/production use.
 *
 * The resolved URL is cached in a module-level variable so subsequent
 * calls (reconnects) use the same endpoint.
 */
let _resolvedSseUrl: string | null = null;

async function resolveSseUrl(): Promise<string> {
  // Capture into a local const so TypeScript can narrow the type
  // (mutable module-level let variables can't be narrowed).
  const cached = _resolvedSseUrl;
  if (cached) return cached;

  // Try local SSE relay first (fast health check)
  if (typeof window !== "undefined") {
    try {
      const resp = await fetch(`${LOCAL_SSE_URL}/health`, {
        signal: AbortSignal.timeout(1000),
      });
      if (resp.ok) {
        const url = `${LOCAL_SSE_URL}/events`;
        _resolvedSseUrl = url;
        return url;
      }
    } catch {
      // Local relay not running — fall through to bridge
    }
  }

  // Fall back to Cloudflare Worker SSE Bridge
  _resolvedSseUrl = SSE_WORKER_URL;
  return SSE_WORKER_URL;
}

function getEventSourceUrl(baseUrl: string): string {
  // Append ?token= for SSE connections (EventSource can't set headers)
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("modellens-token");
    if (token) {
      const sep = baseUrl.includes("?") ? "&" : "?";
      return `${baseUrl}${sep}token=${encodeURIComponent(token)}`;
    }
  }
  return baseUrl;
}

export function useEventStream(url?: string): EventStreamState {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let mounted = true;

    async function connect() {
      if (!mounted) return;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      // Resolve the best SSE endpoint: local relay or Cloudflare bridge
      let resolvedUrl: string;
      if (url) {
        resolvedUrl = url;
      } else {
        resolvedUrl = await resolveSseUrl();
      }

      const es = new EventSource(getEventSourceUrl(resolvedUrl));
      eventSourceRef.current = es;

      // ── Unnamed events handler ─────────────────────────────
      // The Python SSE bridge sends all events WITHOUT an `event:` line,
      // so they all arrive here.  The `_event_type` field discriminates.
      es.onmessage = (event: MessageEvent) => {
        if (!mounted) return;
        try {
          const data = JSON.parse(event.data) as SSEEvent;

          // Track connection state from _status events
          if (data._event_type === "_status" && data.connected !== undefined) {
            setConnected(Boolean(data.connected));
          }

          // Collect the event (unless it's a purely internal status update)
          if (data._event_type !== "_status" || data.connected === undefined) {
            setEvents((prev) => {
              const next = [...prev, data];
              return next.length > MAX_BUFFERED_EVENTS
                ? next.slice(next.length - MAX_BUFFERED_EVENTS)
                : next;
            });
          }
        } catch {
          // Malformed data — skip
        }
      };

      // Connection lost — EventSource will auto-reconnect.
      // If the token has expired, reconnection fails with 401.
      // After 5 seconds of CLOSED state, redirect to /login
      // (the token may have expired but still be in localStorage).
      es.onerror = () => {
        if (mounted) {
          setConnected(false);
          setTimeout(() => {
            if (mounted && es.readyState === EventSource.CLOSED) {
              // Clear cached URL so next reconnect re-probes local relay
              _resolvedSseUrl = null;
              // Token is expired or invalid — redirect to re-auth
              window.localStorage.removeItem("modellens-token");
              window.location.href = "/login";
            }
          }, 5000);
        }
      };
    }

    connect();

    return () => {
      mounted = false;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [url]);

  const clearEvents = useCallback(() => setEvents([]), []);

  const getEventsByType = useCallback(
    (type: string): SSEEvent[] =>
      events.filter((e) => e._event_type === type),
    [events],
  );

  // Derive latestByType from current events
  const latestByType: Record<string, SSEEvent | undefined> = {};
  for (const event of events) {
    latestByType[event._event_type] = event;
  }

  return {
    connected,
    events,
    eventCount: events.length,
    clearEvents,
    getEventsByType,
    latestByType,
  };
}

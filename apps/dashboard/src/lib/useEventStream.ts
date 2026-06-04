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

const SSE_WORKER_URL = import.meta.env.PUBLIC_SSE_WORKER_URL || "/api/events";

export function useEventStream(url: string = SSE_WORKER_URL): EventStreamState {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let mounted = true;

    function connect() {
      if (!mounted) return;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const es = new EventSource(url);
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

      // Connection lost — EventSource will auto-reconnect
      es.onerror = () => {
        if (mounted) setConnected(false);
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

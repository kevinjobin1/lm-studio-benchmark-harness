import React, { useState, useEffect, useRef } from "react";
import { useEventStream } from "../lib/useEventStream";

// ── sessionStorage keys ──────────────────────────────────────────

const STORAGE_KEY_COUNT = "replay-badge-count";
const STORAGE_KEY_NOTIFIED = "replay-badge-notified";

/**
 * ReplaySidebarBadge — subscribes to the live SSE event stream and shows
 * a count badge on the sidebar "Replay Viewer" nav item when new replay
 * sessions are recorded during the current browser session.
 *
 * Persists the count and notified run_ids in sessionStorage so the badge
 * survives page navigations within the same browser tab.
 *
 * Each completed/failed RunLifecycleEvent increments the counter
 * (deduplicated by run_id). Returns null when count is 0 so nothing is
 * rendered until activity occurs.
 */
export default function ReplaySidebarBadge() {
  const { events } = useEventStream();

  // ── Initialise from sessionStorage on mount ─────────────────
  // Auto-clear the badge when the user navigates to /replays
  const [count, setCount] = useState(() => {
    try {
      if (typeof window !== "undefined" && window.location.pathname === "/replays") {
        sessionStorage.removeItem(STORAGE_KEY_COUNT);
        sessionStorage.removeItem(STORAGE_KEY_NOTIFIED);
        return 0;
      }
      const stored = sessionStorage.getItem(STORAGE_KEY_COUNT);
      return stored ? parseInt(stored, 10) || 0 : 0;
    } catch {
      return 0;
    }
  });

  // Persist count whenever it changes
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY_COUNT, String(count));
    } catch {
      // sessionStorage not available
    }
  }, [count]);

  // ── Initialise notified set lazily (runs once, then ref stays) ─
  const notifiedRunIds = useRef<Set<string> | null>(null);
  if (notifiedRunIds.current === null) {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY_NOTIFIED);
      notifiedRunIds.current = stored
        ? new Set(JSON.parse(stored) as string[])
        : new Set<string>();
    } catch {
      notifiedRunIds.current = new Set<string>();
    }
  }

  // ── Watch for new lifecycle events ──────────────────────────
  useEffect(() => {
    if (events.length === 0) return;

    const lastEvent = events[events.length - 1];
    if (lastEvent._event_type !== "RunLifecycleEvent") return;

    const status = lastEvent.status as string;
    if (status !== "completed" && status !== "failed") return;

    const runId = (lastEvent.run_id || "") as string;
    if (!runId || notifiedRunIds.current!.has(runId)) return;

    notifiedRunIds.current!.add(runId);

    // Persist the notified set immediately (refs are synchronous)
    try {
      sessionStorage.setItem(
        STORAGE_KEY_NOTIFIED,
        JSON.stringify([...notifiedRunIds.current!]),
      );
    } catch {
      // sessionStorage not available
    }

    setCount((c) => c + 1);
  }, [events]);

  if (count === 0) return null;

  return (
    <span className="rpv-sidebar-badge" aria-label={`${count} new replays`}>
      {count}
    </span>
  );
}

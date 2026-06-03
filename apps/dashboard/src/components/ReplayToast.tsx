import React, { useState, useEffect, useRef } from "react";
import { useEventStream } from "../lib/useEventStream";

/**
 * ReplayToast — subscribes to the live SSE event stream and shows a
 * non-intrusive toast notification when a benchmark run completes or
 * fails, indicating that a new replay session has been recorded.
 *
 * The toast links to the /replays page so users can open the replay viewer.
 * Auto-dismisses after 6 seconds. Tracks notified run_ids in a ref to
 * avoid duplicate toasts for the same session.
 */
export default function ReplayToast() {
  const { events } = useEventStream();
  const [toast, setToast] = useState<{
    run_id: string;
    status: string;
    model: string;
  } | null>(null);
  const notifiedRunIds = useRef(new Set<string>());
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Watch for RunLifecycleEvent with completed/failed status
  useEffect(() => {
    if (events.length === 0) return;

    const lastEvent = events[events.length - 1];
    if (lastEvent._event_type !== "RunLifecycleEvent") return;

    const status = lastEvent.status as string;
    if (status !== "completed" && status !== "failed") return;

    const runId = (lastEvent.run_id || "") as string;
    if (!runId || notifiedRunIds.current.has(runId)) return;

    notifiedRunIds.current.add(runId);

    // Show toast
    setToast({
      run_id: runId,
      status,
      model: (lastEvent.model as string) || "",
    });

    // Clear previous timer
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);

    // Auto-dismiss after 6 seconds
    toastTimerRef.current = setTimeout(() => {
      setToast(null);
      toastTimerRef.current = null;
    }, 6000);
  }, [events]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  if (!toast) return null;

  const isSuccess = toast.status === "completed";

  return (
    <a
      href={`/replays?run_id=${encodeURIComponent(toast.run_id)}`}
      className={`rpv-toast ${isSuccess ? "rpv-toast-success" : "rpv-toast-error"}`}
      role="status"
      aria-live="polite"
    >
      <div className="rpv-toast-icon-col">
        <span className="material-symbols-outlined">
          {isSuccess ? "check_circle" : "error"}
        </span>
      </div>
      <div className="rpv-toast-body">
        <span className="rpv-toast-title">
          {isSuccess ? "Replay recorded" : "Replay failed"}
        </span>
        <span className="rpv-toast-desc">
          {toast.model && (
            <>
              <strong>{toast.model}</strong>
              {" · "}
            </>
          )}
          {toast.run_id.slice(0, 12)} — {toast.status}
        </span>
      </div>
      <span className="material-symbols-outlined rpv-toast-arrow">
        arrow_forward
      </span>
    </a>
  );
}

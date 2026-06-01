import { useState, useEffect, useRef } from "react";

interface ActiveResponse {
  active: boolean;
  processes: { pid: number; model: string; quick: boolean; startTime: string }[];
}

export default function BenchmarkStatusBadge() {
  const [active, setActive] = useState(false);
  const [model, setModel] = useState<string | null>(null);
  const [pids, setPids] = useState<number[]>([]);
  const [killing, setKilling] = useState(false);
  const [startTime, setStartTime] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState("");
  const [justCompleted, setJustCompleted] = useState(false);
  const [doneModel, setDoneModel] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const prevActive = useRef(false);
  const modelRef = useRef<string | null>(null);
  const badgeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;

    async function poll() {
      try {
        const res = await fetch("/api/run-benchmark/active");
        if (!res.ok) return;
        const data: ActiveResponse = await res.json();
        if (!mounted) return;

        // Detect completion: was running, now idle
        if (prevActive.current && !data.active) {
          setJustCompleted(true);
          setDoneModel(modelRef.current);
          setTimeout(() => setJustCompleted(false), 2500);
        }
        prevActive.current = data.active;

        setActive(data.active);
        const shortModel = data.processes.length > 0 ? data.processes[0].model.split("/").pop() || data.processes[0].model : null;
        setModel(shortModel);
        modelRef.current = shortModel;
        setPids(data.processes.map((p) => p.pid));
        setStartTime(data.processes.length > 0 ? data.processes[0].startTime : null);
      } catch {
        // server unreachable — fall back to idle
        if (mounted) {
          setActive(false);
          setModel(null);
          setPids([]);
          setStartTime(null);
        }
      }
    }

    poll();
    const interval = setInterval(poll, 3000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Tick elapsed time every second when a benchmark is running
  useEffect(() => {
    if (!active || !startTime) {
      setElapsed("");
      return;
    }

    function tick() {
      const diff = Date.now() - new Date(startTime!).getTime();
      const totalSec = Math.floor(diff / 1000);
      const mins = Math.floor(totalSec / 60);
      const secs = totalSec % 60;
      setElapsed(mins > 0 ? `${mins}m ${secs}s` : `${secs}s`);
    }

    tick();
    const clock = setInterval(tick, 1000);
    return () => clearInterval(clock);
  }, [active, startTime]);

  const handleKill = async () => {
    setKilling(true);
    // Fire all kills in parallel — idempotent endpoint handles already-exited PIDs gracefully
    await Promise.allSettled(
      pids.map((pid) =>
        fetch(`/api/run-benchmark/kill?pid=${pid}`, { method: "POST" }).catch(() => {}),
      ),
    );
    // Next poll cycle (≤ 3s) will pick up the killed state and reset the UI
    setKilling(false);
  };

  // Close flyout on outside click
  useEffect(() => {
    if (!expanded) return;
    function handleClick(e: MouseEvent) {
      if (badgeRef.current && !badgeRef.current.contains(e.target as Node)) {
        setExpanded(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [expanded]);

  const showDone = justCompleted && !active;
  const statusLabel = showDone
    ? `DONE ✓ ${doneModel || ""}`
    : active
      ? model
        ? `BENCHMARK RUNNING: ${model}${elapsed ? ` • ${elapsed}` : ""}`
        : "BENCHMARK RUNNING"
      : "NODE: IDLE";

  const hasDetail = active || showDone;

  // Reset expanded when details disappear (done animation finishes)
  useEffect(() => {
    if (!hasDetail) setExpanded(false);
  }, [hasDetail]);

  return (
    <div
      ref={badgeRef}
      className={`node-status ${active ? "node-status-active" : ""} ${showDone ? "node-status-done" : ""} ${expanded ? "node-status-expanded" : ""}`}>
      <div className={`status-dot ${active ? "status-dot-active" : ""} ${showDone ? "status-dot-done" : ""}`} />
      <span className={`status-text ${active ? "status-text-active" : ""} ${showDone ? "status-text-done" : ""}`}>
        {statusLabel}
      </span>
      {active && (
        <button
          className="status-kill-btn"
          onClick={handleKill}
          disabled={killing}
          title="Stop benchmark"
          aria-label="Stop benchmark"
        >
          {killing ? (
            <span className="status-kill-spinner" />
          ) : (
            <span className="material-symbols-outlined status-kill-icon">stop</span>
          )}
        </button>
      )}
      <div className="status-divider" />
      <span
        className={`status-id ${hasDetail ? "status-id-clickable" : ""}`}
        onClick={hasDetail ? () => setExpanded(!expanded) : undefined}
        title={hasDetail ? "Click for details" : undefined}
      >
        APPLE M3 MAX
      </span>
      {active && (
        <div className="status-progress-track">
          <div className="status-progress-bar" />
        </div>
      )}

      {/* ── Flyout details panel ───────────────────────────────── */}
      {expanded && hasDetail && (
        <div className="status-flyout">
          <div className="status-flyout-row">
            <span className="status-flyout-label">Model</span>
            <span className="status-flyout-value">{model || doneModel}</span>
          </div>
          {pids.length > 0 && (
            <div className="status-flyout-row">
              <span className="status-flyout-label">PID</span>
              <span className="status-flyout-value">{pids.join(", ")}</span>
            </div>
          )}
          {elapsed && (
            <div className="status-flyout-row">
              <span className="status-flyout-label">Elapsed</span>
              <span className="status-flyout-value">{elapsed}</span>
            </div>
          )}
          <div className="status-flyout-row">
            <span className="status-flyout-label">Status</span>
            <span className={`status-flyout-value ${active ? "status-flyout-value-running" : ""}`}>
              {active ? "Running" : "Completed"}
            </span>
          </div>
          {pids.length > 0 && (
            <a
              className="status-flyout-link"
              href={`/api/run-benchmark/logs?pid=${pids[0]}`}
              target="_blank"
              rel="noopener"
            >
              <span className="material-symbols-outlined">terminal</span>
              View logs
            </a>
          )}
        </div>
      )}
    </div>
  );
}

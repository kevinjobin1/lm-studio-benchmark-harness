import React, { useState, useCallback, useEffect, useRef } from "react";

type RunState = "idle" | "checking" | "ready" | "running" | "done" | "error";

interface StatusData {
  connected: boolean;
  models: string[];
  error?: string;
}

interface LogData {
  pid: number;
  status: "running" | "exited";
  stdout: string;
  stderr: string;
}

export default function RunBenchmarkButton() {
  const [open, setOpen] = useState(false);
  const [runState, setRunState] = useState<RunState>("idle");
  const [status, setStatus] = useState<StatusData | null>(null);
  const [quick, setQuick] = useState(true);
  const [message, setMessage] = useState("");

  // Live logs state
  const [pid, setPid] = useState<number | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [logStatus, setLogStatus] = useState<"running" | "exited" | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs to bottom on new output
  useEffect(() => {
    if (showLogs && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [stdout, stderr, showLogs]);

  // Poll logs when a benchmark is running
  useEffect(() => {
    if (!pid || (runState !== "running" && runState !== "done")) return;

    let mounted = true;
    let timer: ReturnType<typeof setInterval>;

    async function poll() {
      try {
        const resp = await fetch(`/api/run-benchmark/logs?pid=${pid}`);
        if (!resp.ok) return;
        const data: LogData = await resp.json();
        if (!mounted) return;
        setStdout(data.stdout);
        setStderr(data.stderr);
        setLogStatus(data.status);
        if (data.status === "exited") {
          clearInterval(timer);
        }
      } catch {
        // ignore polling errors
      }
    }

    poll();
    timer = setInterval(poll, 2000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, [pid, runState]);

  // Check LM Studio connection
  const checkStatus = useCallback(async () => {
    setRunState("checking");
    try {
      const resp = await fetch("/api/status");
      const data: StatusData = await resp.json();
      setStatus(data);
      setRunState(data.connected ? "ready" : "error");
      if (!data.connected) {
        setMessage(data.error || "LM Studio not reachable. Start LM Studio and load a model.");
      }
    } catch {
      setStatus({ connected: false, models: [], error: "Network error" });
      setRunState("error");
      setMessage("Could not reach the dashboard API.");
    }
  }, []);

  // Open dialog and check status
  const handleOpen = () => {
    setOpen(true);
    setMessage("");
    setPid(null);
    setShowLogs(false);
    setStdout("");
    setStderr("");
    setLogStatus(null);
    checkStatus();
  };

  // Trigger benchmark
  const handleRun = async () => {
    if (runState === "running" || runState === "checking") return;
    setRunState("running");
    setMessage("Starting benchmark...");
    try {
      const resp = await fetch("/api/run-benchmark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quick }),
      });
      const data = await resp.json();
      if (data.success) {
        setPid(data.pid);
        setShowLogs(true);
        setLogStatus("running");
        setRunState("done");
        setMessage(data.message);
      } else {
        setRunState("error");
        setMessage(data.message);
      }
    } catch {
      setRunState("error");
      setMessage("Failed to start benchmark. Is the server running?");
    }
  };

  // Close dialog
  const handleClose = () => {
    setOpen(false);
    setRunState("idle");
  };

  return (
    <>
      {/* Trigger button */}
      <button className="btn-primary" onClick={handleOpen} title="Run benchmarks">
        <span
          className="material-symbols-outlined"
          style={{ fontSize: 14, marginRight: 4 }}
        >
          terminal
        </span>
        Run new benchmark
      </button>

      {/* Modal overlay */}
      {open && (
        <div className="modal-overlay" onClick={handleClose}>
          <div
            className="modal-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="modal-header">
              <h3
                style={{
                  fontFamily: "var(--font-ui)",
                  fontSize: 16,
                  fontWeight: 600,
                  color: "var(--text-primary)",
                }}
              >
                Run New Benchmark
              </h3>
              <button className="modal-close" onClick={handleClose}>
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {/* Body */}
            <div className="modal-body">
              {/* LM Studio status */}
              <div className="modal-section">
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span
                    className="material-symbols-outlined"
                    style={{
                      fontSize: 18,
                      color:
                        runState === "ready" || runState === "done"
                          ? "var(--success)"
                          : runState === "error"
                            ? "var(--error)"
                            : runState === "running"
                              ? "var(--warning)"
                              : "var(--text-tertiary)",
                    }}
                  >
                    {runState === "checking"
                      ? "sync"
                      : runState === "ready" || runState === "done"
                        ? "check_circle"
                        : runState === "error"
                          ? "error"
                          : runState === "running"
                            ? "play_circle"
                            : "sensors"}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 12,
                      fontWeight: 500,
                      color: "var(--text-secondary)",
                    }}
                  >
                    LM Studio:{" "}
                    {runState === "checking"
                      ? "Checking..."
                      : runState === "ready"
                        ? "Connected"
                        : runState === "error"
                          ? "Not connected"
                          : runState === "running"
                            ? "Running..."
                            : "Idle"}
                  </span>
                  {pid && (
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        color: "var(--text-tertiary)",
                        marginLeft: "auto",
                      }}
                    >
                      PID {pid}
                    </span>
                  )}
                </div>

                {status?.models && status.models.length > 0 && (
                  <div
                    style={{
                      background: "var(--bg-low)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-sm)",
                      padding: "0.5rem 0.75rem",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        color: "var(--text-tertiary)",
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                      }}
                    >
                      Loaded models
                    </span>
                    <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 2 }}>
                      {status.models.map((m) => (
                        <code
                          key={m}
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 11,
                            color: "var(--brand-primary)",
                          }}
                        >
                          {m}
                        </code>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Quick mode toggle */}
              <div className="modal-section">
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={quick}
                    onChange={(e) => setQuick(e.target.checked)}
                    style={{ accentColor: "var(--brand-primary)" }}
                  />
                  <span
                    style={{
                      fontFamily: "var(--font-ui)",
                      fontSize: 13,
                      color: "var(--text-primary)",
                    }}
                  >
                    Quick mode (fewer samples, faster)
                  </span>
                </label>
              </div>

              {/* Message */}
              {message && (
                <div
                  style={{
                    padding: "0.75rem",
                    background:
                      runState === "done"
                        ? "rgba(78, 222, 163, 0.08)"
                        : runState === "error"
                          ? "rgba(255, 180, 171, 0.08)"
                          : "var(--bg-low)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color:
                      runState === "done"
                        ? "var(--success)"
                        : runState === "error"
                          ? "var(--error)"
                          : "var(--text-secondary)",
                    lineHeight: 1.5,
                  }}
                >
                  {message}
                </div>
              )}

              {/* Live Logs Section */}
              {pid && (
                <div className="modal-section">
                  <button
                    className="btn-outline"
                    onClick={() => setShowLogs(!showLogs)}
                    style={{ width: "100%", justifyContent: "space-between" }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                        terminal
                      </span>
                      <span>Live Output</span>
                      {logStatus === "running" && (
                        <span
                          style={{
                            display: "inline-block",
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: "var(--success)",
                            animation: "pulse-dot 2s ease-in-out infinite",
                          }}
                        />
                      )}
                      {logStatus === "exited" && (
                        <span className="chip chip-success" style={{ fontSize: 9 }}>
                          DONE
                        </span>
                      )}
                    </span>
                    <span
                      className="material-symbols-outlined"
                      style={{
                        fontSize: 18,
                        transform: showLogs ? "rotate(180deg)" : "none",
                        transition: "transform 0.2s",
                      }}
                    >
                      expand_more
                    </span>
                  </button>

                  {showLogs && (
                    <div
                      className="logs-terminal animate-entrance"
                      style={{
                        marginTop: 8,
                        background: "var(--bg-lowest)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "var(--radius-sm)",
                        padding: "0.75rem",
                        maxHeight: 280,
                        overflowY: "auto",
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        lineHeight: 1.6,
                        color: "var(--text-secondary)",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                      }}
                    >
                      {stdout ? (
                        <>
                          {stdout}
                          {stderr && (
                            <>
                              {"\n"}
                              <span
                                style={{ color: "var(--error)" }}
                              >
                                {stderr}
                              </span>
                            </>
                          )}
                        </>
                      ) : (
                        <span style={{ color: "var(--text-tertiary)", fontStyle: "italic" }}>
                          Waiting for output...
                        </span>
                      )}
                      <div ref={logEndRef} />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="modal-footer">
              <button className="btn-outline" onClick={handleClose}>
                {runState === "done" ? "Close" : "Cancel"}
              </button>
              <button
                className="btn-primary"
                onClick={handleRun}
                disabled={
                  runState !== "ready" && runState !== "error" && runState !== "done"
                }
                style={{
                  opacity:
                    runState !== "ready" && runState !== "error" && runState !== "done"
                      ? 0.5
                      : 1,
                }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ fontSize: 14, marginRight: 4 }}
                >
                  {runState === "running" ? "sync" : "play_arrow"}
                </span>
                {runState === "running" ? "Running..." : "Run Benchmark"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .modal-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 100;
          animation: fadeIn 0.15s ease-out;
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .modal-dialog {
          background: var(--bg-container);
          border: 1px solid var(--border-default);
          border-radius: var(--radius-md);
          width: 520px;
          max-width: 92vw;
          max-height: 85vh;
          display: flex;
          flex-direction: column;
          animation: slideUp 0.2s ease-out;
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .modal-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 1.25rem 1.5rem 0.75rem;
          border-bottom: 1px solid var(--border-subtle);
          flex-shrink: 0;
        }
        .modal-close {
          background: none;
          border: none;
          color: var(--text-tertiary);
          cursor: pointer;
          padding: 4px;
          border-radius: var(--radius-sm);
          transition: color 0.15s;
          display: flex;
        }
        .modal-close:hover {
          color: var(--text-primary);
        }

        .modal-body {
          padding: 1.25rem 1.5rem;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
          overflow-y: auto;
          flex: 1;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 0.5rem;
          padding: 1rem 1.5rem;
          border-top: 1px solid var(--border-subtle);
          flex-shrink: 0;
        }

        .logs-terminal::-webkit-scrollbar { width: 4px; }
        .logs-terminal::-webkit-scrollbar-track { background: transparent; }
        .logs-terminal::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 2px; }
      `}</style>
    </>
  );
}

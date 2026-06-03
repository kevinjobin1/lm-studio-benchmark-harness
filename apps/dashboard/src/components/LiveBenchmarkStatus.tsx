import React, { useRef, useEffect, useMemo } from "react";
import { useEventStream } from "../lib/useEventStream";
import type { SSEEvent } from "../lib/useEventStream";

// ── Constants ─────────────────────────────────────────────────────

const MAX_VISIBLE_TOKENS = 50;

// ── Helpers ───────────────────────────────────────────────────────

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

function formatNum(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toFixed(1);
}

function safeStr(v: unknown, fallback: string = ""): string {
  if (typeof v === "string") return v;
  return fallback;
}

function safeNum(v: unknown, fallback: number = 0): number {
  if (typeof v === "number") return v;
  return fallback;
}

function safeBool(v: unknown, fallback: boolean = false): boolean {
  if (typeof v === "boolean") return v;
  return fallback;
}

// ── Component ─────────────────────────────────────────────────────

export default function LiveBenchmarkStatus() {
  const { connected, events, eventCount, clearEvents } = useEventStream();
  const tokenEndRef = useRef<HTMLDivElement>(null);

  // Derived state from latest events of each type
  const latestLifecycle: SSEEvent | null = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i]._event_type === "RunLifecycleEvent") return events[i];
    }
    return null;
  }, [events]);

  const latestCompletion: SSEEvent | null = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i]._event_type === "CompletionEvent") return events[i];
    }
    return null;
  }, [events]);

  const latestMetric: SSEEvent | null = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i]._event_type === "MetricEvent" && safeStr(events[i].name, "").includes("score")) {
        return events[i];
      }
    }
    return null;
  }, [events]);

  const latestError: SSEEvent | null = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i]._event_type === "ErrorEvent") return events[i];
    }
    return null;
  }, [events]);

  // Token stream: collect most recent tokens
  const recentTokens: string[] = useMemo(() => {
    const tokens: string[] = [];
    for (let i = events.length - 1; i >= 0 && tokens.length < MAX_VISIBLE_TOKENS; i--) {
      if (events[i]._event_type === "TokenGeneratedEvent") {
        tokens.unshift(safeStr(events[i].token));
      }
    }
    return tokens;
  }, [events]);

  // Auto-scroll token stream
  useEffect(() => {
    if (tokenEndRef.current) {
      tokenEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [recentTokens]);

  // Model name from the most recent lifecycle or completion event
  const modelName = safeStr(latestCompletion?.model) || safeStr(latestLifecycle?.model) || "\u2014";

  // Lifecycle status
  const lifecycleStatus = safeStr(latestLifecycle?.status);
  const isRunning = lifecycleStatus === "started" || lifecycleStatus === "running";
  const isCompleted = lifecycleStatus === "completed";
  const isFailed = lifecycleStatus === "failed" || latestError !== null;

  // Latest TTFT and TPS from completion event
  const ttftMs = safeNum(latestCompletion?.ttft_ms);
  const tps = safeNum(latestCompletion?.tokens_per_second);

  // Latest score from metric event
  const score = safeNum(latestMetric?.value);

  // Token event count
  const tokenCount = events.filter((e) => e._event_type === "TokenGeneratedEvent").length;

  // Connection status color
  const statusColor = isFailed
    ? "var(--error)"
    : isRunning
      ? "var(--warning)"
      : connected
        ? "var(--success)"
        : "var(--text-tertiary)";
  const statusLabel = isFailed ? "Failed" : isRunning ? "Running" : connected ? "Connected" : "Disconnected";

  // Completion success flag
  const completionSuccess = safeBool(latestCompletion?.success);

  // Completion tokens / latency / tps for summary bar
  const compTokens = safeNum(latestCompletion?.tokens_used);
  const compLatency = safeNum(latestCompletion?.latency_ms);
  const compTps = safeNum(latestCompletion?.tokens_per_second);

  return (
    <div className="live-benchmark-panel">
      {/* Header */}
      <div className="lbp-header">
        <div className="lbp-header-left">
          <div
            className="lbp-status-dot"
            style={{ background: statusColor, boxShadow: `0 0 8px ${statusColor}40` }}
          />
          <div className="lbp-header-info">
            <span className="lbp-model-name">{modelName}</span>
            <span className="lbp-status-label">{statusLabel}</span>
          </div>
        </div>
        <div className="lbp-header-right">
          <span className="lbp-event-count mono-label">{eventCount} events</span>
          {eventCount > 0 && (
            <button className="lbp-clear-btn" onClick={clearEvents} title="Clear events" aria-label="Clear events">
              <span className="material-symbols-outlined">delete</span>
            </button>
          )}
        </div>
      </div>

      {/* Metrics row */}
      <div className="lbp-metrics">
        <div className="lbp-metric-card">
          <span className="lbp-metric-label mono-label">TTFT</span>
          <span className={`lbp-metric-value ${ttftMs > 0 ? "lbp-metric-active" : ""}`}>
            {ttftMs > 0 ? formatMs(ttftMs) : "\u2014"}
          </span>
        </div>
        <div className="lbp-metric-card">
          <span className="lbp-metric-label mono-label">Tok/s</span>
          <span className={`lbp-metric-value ${tps > 0 ? "lbp-metric-active" : ""}`}>
            {tps > 0 ? formatNum(tps) : "\u2014"}
          </span>
        </div>
        <div className="lbp-metric-card">
          <span className="lbp-metric-label mono-label">Score</span>
          <span className={`lbp-metric-value ${score > 0 ? "lbp-metric-active" : ""}`}>
            {score > 0 ? `${(score * 100).toFixed(1)}%` : "\u2014"}
          </span>
        </div>
        <div className="lbp-metric-card">
          <span className="lbp-metric-label mono-label">Tokens</span>
          <span className={`lbp-metric-value ${tokenCount > 0 ? "lbp-metric-active" : ""}`}>
            {tokenCount}
          </span>
        </div>
      </div>

      {/* Token stream */}
      <div className="lbp-token-stream">
        <div className="lbp-token-header">
          <span className="mono-label">Token Stream</span>
          {recentTokens.length > 0 && (
            <span className="lbp-token-count">{recentTokens.length} recent</span>
          )}
        </div>
        <div className="lbp-token-content">
          {recentTokens.length > 0 ? (
            <span className="lbp-token-text">
              {recentTokens.join("")}
              <span className="lbp-cursor" />
            </span>
          ) : (
            <span className="lbp-token-placeholder">
              {connected ? "Waiting for tokens\u2026" : "Connect to a running benchmark to see live tokens."}
            </span>
          )}
          <div ref={tokenEndRef} />
        </div>
      </div>

      {/* Error banner */}
      {latestError && (
        <div className="lbp-error-banner">
          <span className="material-symbols-outlined lbp-error-icon">error</span>
          <div className="lbp-error-info">
            <span className="lbp-error-type">{safeStr(latestError.exception, "Error")}</span>
            <span className="lbp-error-msg">{safeStr(latestError.message)}</span>
          </div>
        </div>
      )}

      {/* Completion summary */}
      {latestCompletion && completionSuccess && (
        <div className="lbp-completion-bar">
          <span className="material-symbols-outlined lbp-completion-icon">check_circle</span>
          <div className="lbp-completion-info">
            <span className="lbp-completion-label">Response generated</span>
            <span className="lbp-completion-meta">
              {compTokens} tokens \u00b7 {formatMs(compLatency)} \u00b7 {formatNum(compTps)} tok/s
            </span>
          </div>
        </div>
      )}

      {/* Lifecycle events summary */}
      {events.filter((e) => e._event_type === "RunLifecycleEvent").length > 0 && (
        <div className="lbp-lifecycle-bar">
          <span className="mono-label">Lifecycle</span>
          <div className="lbp-lifecycle-events">
            {events
              .filter((e) => e._event_type === "RunLifecycleEvent")
              .slice(-5)
              .map((e, i) => {
                const status = safeStr(e.status);
                return (
                  <span
                    key={i}
                    className={`lbp-lifecycle-chip ${
                      status === "started" || status === "running"
                        ? "chip-warning"
                        : status === "completed"
                          ? "chip-success"
                          : status === "failed"
                            ? "chip-error"
                            : ""
                    }`}
                  >
                    {status}
                  </span>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}

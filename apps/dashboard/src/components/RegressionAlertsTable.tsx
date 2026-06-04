import React, { useState, useMemo, useEffect, useCallback } from "react";
import ErrorBoundary from "./ErrorBoundary";

// ── Types ─────────────────────────────────────────────────────────

interface RegressionAlert {
  model: string;
  metric: string;
  severity: string;
  direction: string;
  confidence: number;
  change_magnitude: number;
  previous_avg: number | null;
  current_value: number | null;
  baseline_std: number | null;
  z_score: number | null;
  window_size: number;
  timestamp: string;
  run_id: string;
}

interface RegressionStats {
  total: number;
  critical: number;
  warning: number;
  info: number;
  model_count: number;
  metric_count: number;
  latest_alert: string | null;
}

interface RegressionResponse {
  stats: RegressionStats;
  alerts: RegressionAlert[];
}

type SortKey = "severity" | "timestamp" | "change_magnitude" | "z_score" | "model" | "metric";
type SeverityFilter = "all" | "critical" | "warning" | "info";
type DirectionFilter = "all" | "degradation" | "improvement";

// ── Helpers ───────────────────────────────────────────────────────

function getSeverityMeta(severity: string): { label: string; cls: string; icon: string } {
  switch (severity) {
    case "critical":
      return { label: "CRITICAL", cls: "rg-sev-critical", icon: "error" };
    case "warning":
      return { label: "WARNING", cls: "rg-sev-warning", icon: "warning" };
    case "info":
      return { label: "INFO", cls: "rg-sev-info", icon: "info" };
    default:
      return { label: severity.toUpperCase(), cls: "", icon: "help" };
  }
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function formatDelta(pct: number): string {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

const SKELETON_ROWS = 5;

// ── Severity Dot (tiny inline SVG chart) ──────────────────────────

function SeverityDot({ severity, size = 8 }: { severity: string; size?: number }) {
  const color =
    severity === "critical"
      ? "var(--error)"
      : severity === "warning"
        ? "var(--warning)"
        : "var(--success)";
  return (
    <span
      className="rg-severity-dot"
      style={{
        display: "inline-block",
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
      }}
      title={severity}
    />
  );
}

// ── Mini Bar (inline sparkline-like bar) ──────────────────────────

function MiniBar({ pct, severity }: { pct: number; severity: string }) {
  const clamped = Math.min(Math.abs(pct), 100);
  const color =
    severity === "critical"
      ? "var(--error)"
      : severity === "warning"
        ? "var(--warning)"
        : pct > 0
          ? "var(--success)"
          : "var(--brand-primary)";
  return (
    <div className="rg-mini-bar-track">
      <div
        className="rg-mini-bar-fill"
        style={{
          width: `${clamped}%`,
          background: color,
        }}
      />
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────

export default function RegressionAlertsTable({ loading }: { loading?: boolean }) {
  const [data, setData] = useState<RegressionResponse | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("severity");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>("all");
  const [modelSearch, setModelSearch] = useState("");

  // ── Fetch data ──────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    setFetchError(null);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (severityFilter !== "all") params.set("severity", severityFilter);
      const res = await fetch(`/api/regression?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: RegressionResponse = await res.json();
      setData(json);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Failed to load regression data");
      setData(null);
    }
  }, [severityFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Filter & sort ───────────────────────────────────────────────
  const filtered = useMemo(() => {
    if (!data) return [];
    let items = [...data.alerts];

    if (directionFilter !== "all") {
      items = items.filter((a) => a.direction === directionFilter);
    }
    if (modelSearch.trim()) {
      const q = modelSearch.toLowerCase();
      items = items.filter((a) => a.model.toLowerCase().includes(q));
    }

    const sevOrder: Record<string, number> = { critical: 0, warning: 1, info: 2 };
    items.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "severity":
          cmp = (sevOrder[a.severity] ?? 99) - (sevOrder[b.severity] ?? 99);
          break;
        case "timestamp":
          cmp = a.timestamp.localeCompare(b.timestamp);
          break;
        case "change_magnitude":
          cmp = a.change_magnitude - b.change_magnitude;
          break;
        case "z_score":
          cmp = Math.abs(a.z_score ?? 0) - Math.abs(b.z_score ?? 0);
          break;
        case "model":
          cmp = a.model.localeCompare(b.model);
          break;
        case "metric":
          cmp = a.metric.localeCompare(b.metric);
          break;
      }
      return sortDir === "desc" ? -cmp : cmp;
    });

    return items;
  }, [data, sortKey, sortDir, directionFilter, modelSearch]);

  // ── Toggle sort ─────────────────────────────────────────────────
  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  // ── Loading state ───────────────────────────────────────────────
  if (loading) {
    return (
      <div className="rg-wrapper">
        <div className="rg-stats-grid">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card rg-stat-card">
              <div className="skeleton-pulse" style={{ width: 28, height: 28, borderRadius: "50%", marginBottom: 8 }} />
              <div className="skeleton-pulse" style={{ width: 60, height: 24, borderRadius: "var(--radius-sm)", marginBottom: 4 }} />
              <div className="skeleton-pulse" style={{ width: 80, height: 12, borderRadius: "var(--radius-sm)" }} />
            </div>
          ))}
        </div>
        <div className="card" style={{ padding: 0, overflow: "hidden", marginTop: "1.5rem" }}>
          <div className="rg-table-header">
            <h3>Regression Alerts</h3>
          </div>
          <div className="rg-table-wrapper">
            <table className="rg-table">
              <thead>
                <tr>
                  {["Severity", "Model", "Metric", "Direction", "Change", "Z-Score", "Confidence", "Timestamp"].map((h) => (
                    <th key={h} className="rg-th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
                  <tr key={i}>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 70, height: 20, borderRadius: "var(--radius-sm)" }} /></td>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 120, height: 14, borderRadius: "var(--radius-sm)" }} /></td>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 100, height: 14, borderRadius: "var(--radius-sm)" }} /></td>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 50, height: 14, borderRadius: "var(--radius-sm)" }} /></td>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 60, height: 14, borderRadius: "var(--radius-sm)" }} /></td>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 50, height: 14, borderRadius: "var(--radius-sm)" }} /></td>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 50, height: 14, borderRadius: "var(--radius-sm)" }} /></td>
                    <td className="rg-td"><span className="skeleton-pulse" style={{ display: "inline-block", width: 80, height: 14, borderRadius: "var(--radius-sm)" }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="rg-wrapper">
        {/* ═══ Stats Summary Cards ═══════════════════════════════════ */}
        <div className="rg-stats-grid animate-entrance" style={{ animationDelay: "0.1s" }}>
          <div className="card rg-stat-card">
            <span className="material-symbols-outlined rg-stat-icon" style={{ color: "var(--brand-primary)" }}>report</span>
            <div className="rg-stat-value">{data?.stats.total ?? 0}</div>
            <div className="rg-stat-label">Total Alerts</div>
          </div>
          <div className="card rg-stat-card">
            <span className="material-symbols-outlined rg-stat-icon" style={{ color: "var(--error)" }}>cancel</span>
            <div className="rg-stat-value rg-stat-critical">{data?.stats.critical ?? 0}</div>
            <div className="rg-stat-label">Critical</div>
          </div>
          <div className="card rg-stat-card">
            <span className="material-symbols-outlined rg-stat-icon" style={{ color: "var(--warning)" }}>warning</span>
            <div className="rg-stat-value rg-stat-warning">{data?.stats.warning ?? 0}</div>
            <div className="rg-stat-label">Warning</div>
          </div>
          <div className="card rg-stat-card">
            <span className="material-symbols-outlined rg-stat-icon" style={{ color: "var(--success)" }}>check_circle</span>
            <div className="rg-stat-value rg-stat-info">{data?.stats.info ?? 0}</div>
            <div className="rg-stat-label">Info</div>
          </div>
          <div className="card rg-stat-card">
            <span className="material-symbols-outlined rg-stat-icon" style={{ color: "var(--text-tertiary)" }}>dns</span>
            <div className="rg-stat-value">{data?.stats.model_count ?? 0}</div>
            <div className="rg-stat-label">Models</div>
          </div>
          <div className="card rg-stat-card">
            <span className="material-symbols-outlined rg-stat-icon" style={{ color: "var(--text-tertiary)" }}>speed</span>
            <div className="rg-stat-value">{data?.stats.metric_count ?? 0}</div>
            <div className="rg-stat-label">Metrics Tracked</div>
          </div>
        </div>

        {/* ═══ Error State ═══════════════════════════════════════════ */}
        {fetchError && (
          <div className="card rg-error-card animate-entrance" style={{ animationDelay: "0.15s" }}>
            <span className="material-symbols-outlined" style={{ color: "var(--error)", fontSize: 24 }}>error</span>
            <div>
              <div className="rg-error-title">Failed to load regression data</div>
              <div className="rg-error-detail">{fetchError}</div>
            </div>
            <button className="btn-outline" onClick={fetchData}>Retry</button>
          </div>
        )}

        {/* ═══ Empty State ═══════════════════════════════════════════ */}
        {!fetchError && data && data.alerts.length === 0 && (
          <div className="card empty-state animate-entrance" style={{ animationDelay: "0.15s", marginTop: "1.5rem" }}>
            <span className="material-symbols-outlined empty-state-icon">monitoring</span>
            <h3>No Regression Alerts</h3>
            <p className="text-balance">
              All model metrics are stable. Run benchmarks to populate the metrics database — regressions are automatically detected after each completed run.
            </p>
            <div className="rg-code-block" style={{ marginTop: "1rem", display: "inline-flex" }}>
              <code>modellens regression detect --all</code>
            </div>
          </div>
        )}

        {/* ═══ Alert Table ═══════════════════════════════════════════ */}
        {!fetchError && data && data.alerts.length > 0 && (
          <div className="card animate-entrance" style={{ padding: 0, overflow: "hidden", marginTop: "1.5rem", animationDelay: "0.2s" }}>
            {/* ── Filters ─────────────────────────────────────── */}
            <div className="rg-table-header">
              <h3>Regression Alerts</h3>
              <div className="rg-filters">
                <div className="rg-filter-group">
                  <label htmlFor="rg-severity-filter" className="rg-filter-label">Severity</label>
                  <select
                    id="rg-severity-filter"
                    className="rg-filter-select"
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value as SeverityFilter)}
                  >
                    <option value="all">All</option>
                    <option value="critical">Critical</option>
                    <option value="warning">Warning</option>
                    <option value="info">Info</option>
                  </select>
                </div>
                <div className="rg-filter-group">
                  <label htmlFor="rg-direction-filter" className="rg-filter-label">Direction</label>
                  <select
                    id="rg-direction-filter"
                    className="rg-filter-select"
                    value={directionFilter}
                    onChange={(e) => setDirectionFilter(e.target.value as DirectionFilter)}
                  >
                    <option value="all">All</option>
                    <option value="degradation">Degradation</option>
                    <option value="improvement">Improvement</option>
                  </select>
                </div>
                <div className="rg-filter-group">
                  <label htmlFor="rg-model-search" className="rg-filter-label">Search Model</label>
                  <input
                    id="rg-model-search"
                    className="rg-filter-input"
                    type="text"
                    placeholder="e.g. qwen..."
                    value={modelSearch}
                    onChange={(e) => setModelSearch(e.target.value)}
                  />
                </div>
                <button className="rg-refresh-btn" onClick={fetchData} title="Refresh">
                  <span className="material-symbols-outlined">refresh</span>
                </button>
              </div>
            </div>

            {/* ── Table ──────────────────────────────────────────── */}
            <div className="rg-table-wrapper">
              {filtered.length === 0 ? (
                <div className="rg-no-results">
                  <span className="material-symbols-outlined" style={{ fontSize: 24, color: "var(--text-tertiary)" }}>search_off</span>
                  <span>No alerts match the current filters</span>
                </div>
              ) : (
                <table className="rg-table">
                  <thead>
                    <tr>
                      <th className="rg-th rg-th-sort" onClick={() => handleSort("severity")}>
                        Severity {sortKey === "severity" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                      </th>
                      <th className="rg-th rg-th-sort" onClick={() => handleSort("model")}>
                        Model {sortKey === "model" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                      </th>
                      <th className="rg-th rg-th-sort" onClick={() => handleSort("metric")}>
                        Metric {sortKey === "metric" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                      </th>
                      <th className="rg-th">Direction</th>
                      <th className="rg-th rg-th-sort" onClick={() => handleSort("change_magnitude")}>
                        Change {sortKey === "change_magnitude" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                      </th>
                      <th className="rg-th">Bar</th>
                      <th className="rg-th rg-th-sort" onClick={() => handleSort("z_score")}>
                        Z-Score {sortKey === "z_score" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                      </th>
                      <th className="rg-th">Confidence</th>
                      <th className="rg-th rg-th-sort" onClick={() => handleSort("timestamp")}>
                        Timestamp {sortKey === "timestamp" ? (sortDir === "desc" ? "↓" : "↑") : ""}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((alert, i) => {
                      const sev = getSeverityMeta(alert.severity);
                      const dirIcon = alert.direction === "degradation" ? "arrow_downward" : "arrow_upward";
                      const dirColor = alert.direction === "degradation" ? "var(--error)" : "var(--success)";
                      return (
                        <tr key={`${alert.model}-${alert.metric}-${alert.timestamp}-${i}`}>
                          <td className="rg-td">
                            <span className={`rg-severity-badge ${sev.cls}`}>
                              <span className="material-symbols-outlined rg-sev-icon">{sev.icon}</span>
                              {sev.label}
                            </span>
                          </td>
                          <td className="rg-td">
                            <span className="rg-model-name">{alert.model}</span>
                          </td>
                          <td className="rg-td">
                            <span className="rg-metric-chip">{alert.metric}</span>
                          </td>
                          <td className="rg-td">
                            <span className="rg-direction" style={{ color: dirColor }}>
                              <span className="material-symbols-outlined rg-dir-icon">{dirIcon}</span>
                              {alert.direction === "degradation" ? "DE" : "IM"}
                            </span>
                          </td>
                          <td className="rg-td rg-td-num">
                            <span
                              className="rg-delta"
                              style={{
                                color: alert.direction === "degradation"
                                  ? (alert.change_magnitude > 20 ? "var(--error)" : "var(--warning)")
                                  : "var(--success)"
                              }}
                            >
                              {formatDelta(alert.direction === "degradation" ? -alert.change_magnitude : alert.change_magnitude)}
                            </span>
                          </td>
                          <td className="rg-td rg-td-bar">
                            <MiniBar pct={alert.change_magnitude} severity={alert.severity} />
                          </td>
                          <td className="rg-td rg-td-num">
                            <span className="rg-zscore" style={{
                              color: Math.abs(alert.z_score ?? 0) > 3 ? "var(--error)" : Math.abs(alert.z_score ?? 0) > 2 ? "var(--warning)" : "var(--text-secondary)"
                            }}>
                              {alert.z_score?.toFixed(2) ?? "—"}
                            </span>
                          </td>
                          <td className="rg-td rg-td-num">
                            <span className="rg-confidence">{`${(alert.confidence * 100).toFixed(0)}%`}</span>
                          </td>
                          <td className="rg-td rg-td-ts">
                            <div className="rg-timestamp">
                              <SeverityDot severity={alert.severity} size={6} />
                              <span>{formatTimestamp(alert.timestamp)}</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* ── Footnote ─────────────────────────────────────────── */}
            <div className="rg-footnote">
              <span className="material-symbols-outlined rg-footnote-icon">monitoring</span>
              <span className="rg-footnote-text">
                {filtered.length} alert{filtered.length !== 1 ? "s" : ""}
                {data?.stats.total !== filtered.length ? ` (filtered from ${data?.stats.total})` : ""}
                {" · "}Auto-detected after benchmark runs via CUSUM change-point detection
              </span>
              <a href="/api/regression" className="rg-api-link" target="_blank" rel="noopener noreferrer">
                <span className="material-symbols-outlined">open_in_new</span>
                API
              </a>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}

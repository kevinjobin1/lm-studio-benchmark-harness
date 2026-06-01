import React, { useEffect, useState } from "react";
import type { BenchmarkResult, ModelSummary } from "../lib/loadResults";
import {
  loadResults,
  groupByModel,
  buildLeaderboard,
} from "../lib/loadResults";
import FailureHeatmap from "./FailureHeatmap";

interface ModelDetailProps {
  modelId: string;
}

export default function ModelDetail({ modelId }: ModelDetailProps) {
  const [bestRun, setBestRun] = useState<BenchmarkResult | null>(null);
  const [modelRuns, setModelRuns] = useState<BenchmarkResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const results = await loadResults();
        const grouped = groupByModel(results);
        const runs = grouped.get(modelId) || [];

        if (runs.length === 0) {
          window.location.href = "/";
          return;
        }

        setModelRuns(runs);
        setBestRun(
          runs.reduce((a, b) =>
            a.metrics.overall_score > b.metrics.overall_score ? a : b,
          ),
        );
      } catch {
        // fallback — redirect
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [modelId]);

  if (loading) {
    return (
      <div className="empty-state">
        <p>Loading model data...</p>
      </div>
    );
  }

  if (!bestRun) {
    return (
      <div className="empty-state">
        <p>Model not found: {modelId}</p>
      </div>
    );
  }

  const overallPct = (bestRun.metrics.overall_score * 100).toFixed(1);
  const totalFailures = Object.values(bestRun.failures).reduce(
    (a, b) => a + b,
    0,
  );

  const scoreCategories = [
    { label: "Coding", value: bestRun.metrics.coding_score, emoji: "💻" },
    { label: "Reasoning", value: bestRun.metrics.reasoning_score, emoji: "🧠" },
    {
      label: "Instructions",
      value: bestRun.metrics.instruction_score,
      emoji: "📋",
    },
    { label: "Frontend", value: bestRun.metrics.frontend_score, emoji: "🎨" },
    { label: "Math", value: bestRun.metrics.math_score, emoji: "📐" },
    { label: "Debugging", value: bestRun.metrics.debugging_score, emoji: "🔧" },
  ];

  function barColor(v: number) {
    return v >= 0.8
      ? "var(--success)"
      : v >= 0.6
        ? "var(--brand-primary)"
        : v >= 0.4
          ? "var(--warning)"
          : "var(--error)";
  }

  return (
    <>
      {/* Header */}
      <section className="page-hero" style={{ paddingTop: 16 }}>
        <h1>{modelId}</h1>
        <p>
          {bestRun.model_metadata.size && `${bestRun.model_metadata.size} · `}
          {bestRun.model_metadata.quantization &&
            `${bestRun.model_metadata.quantization} · `}
          Overall: <strong>{overallPct}%</strong> · {bestRun.stats.runs} runs
        </p>
      </section>

      {/* Score Breakdown */}
      <section style={{ marginBottom: 48 }}>
        <div className="section-header">
          <h2>Score Breakdown</h2>
          <p>Performance across all evaluation categories</p>
        </div>
        <div className="grid-3">
          {scoreCategories.map((s) => (
            <div key={s.label} className="metric-card card">
              <span className="metric-emoji">{s.emoji}</span>
              <span className="metric-label-big">{s.label}</span>
              <span className="metric-value-big">
                {(s.value * 100).toFixed(1)}%
              </span>
              <div className="metric-bar-track" style={{ marginTop: 8 }}>
                <div
                  className="metric-bar-fill"
                  style={{
                    width: `${s.value * 100}%`,
                    background: barColor(s.value),
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Performance */}
      <section style={{ marginBottom: 48 }}>
        <div className="section-header">
          <h2>Performance</h2>
          <p>
            Latency and throughput on {bestRun.hardware.processor} (
            {bestRun.hardware.memory_gb}GB)
          </p>
        </div>
        <div className="grid-2">
          <div className="card">
            <div className="perf-group">
              <div className="perf-stat">
                <span className="perf-stat-label">Tokens/sec</span>
                <span className="perf-stat-value">
                  {bestRun.performance.tokens_per_sec.toFixed(0)}
                </span>
              </div>
              <div className="perf-stat">
                <span className="perf-stat-label">Normalized t/s</span>
                <span className="perf-stat-value">
                  {bestRun.performance.normalized_tps.toFixed(0)}
                </span>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="perf-group">
              <div className="perf-stat">
                <span className="perf-stat-label">TTFT</span>
                <span className="perf-stat-value">
                  {bestRun.performance.ttft_ms.toFixed(0)}
                  <span style={{ fontSize: "0.5em" }}>ms</span>
                </span>
              </div>
              <div className="perf-stat">
                <span className="perf-stat-label">Total Latency</span>
                <span className="perf-stat-value">
                  {bestRun.performance.total_latency_ms.toFixed(0)}
                  <span style={{ fontSize: "0.5em" }}>ms</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Run Stats */}
      <section style={{ marginBottom: 48 }}>
        <div className="section-header">
          <h2>Statistical Summary</h2>
          <p>
            Across {bestRun.stats.runs} runs
            {bestRun.seed ? ` with seed=${bestRun.seed}` : ""}
          </p>
        </div>
        <div className="card">
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-label">Mean</span>
              <span className="stat-value">
                {bestRun.stats.mean.toFixed(3)}
              </span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Std Dev</span>
              <span className="stat-value">
                ±{bestRun.stats.std.toFixed(3)}
              </span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Min</span>
              <span className="stat-value">{bestRun.stats.min.toFixed(3)}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Max</span>
              <span className="stat-value">{bestRun.stats.max.toFixed(3)}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Median</span>
              <span className="stat-value">
                {bestRun.stats.median.toFixed(3)}
              </span>
            </div>
            <div className="stat-item">
              <span className="stat-label">CoV</span>
              <span className="stat-value">
                {bestRun.stats.coefficient_of_variation.toFixed(3)}
              </span>
            </div>
          </div>
          {bestRun.stats.confidence_95 && (
            <div className="confidence-interval">
              <span>
                95% CI: [{bestRun.stats.confidence_95[0].toFixed(3)},{" "}
                {bestRun.stats.confidence_95[1].toFixed(3)}]
              </span>
            </div>
          )}
        </div>
      </section>

      {/* Failures */}
      <section style={{ marginBottom: 48 }}>
        <div className="section-header">
          <h2>Failure Breakdown</h2>
          <p>{totalFailures} total issues detected across all runs</p>
        </div>
        <div className="card" style={{ height: 380 }}>
          <div style={{ height: 300 }}>
            <FailureHeatmap results={modelRuns} />
          </div>
        </div>
      </section>

      {/* Metadata */}
      <section style={{ marginBottom: 48 }}>
        <div className="section-header">
          <h2>Reproducibility</h2>
        </div>
        <div className="card">
          <div className="meta-grid">
            <div className="meta-item">
              <span className="meta-label">Run ID</span>
              <code>{bestRun.run_id}</code>
            </div>
            <div className="meta-item">
              <span className="meta-label">Git SHA</span>
              <code>{bestRun.git_sha}</code>
            </div>
            <div className="meta-item">
              <span className="meta-label">Git Branch</span>
              <code>{bestRun.git_branch}</code>
            </div>
            <div className="meta-item">
              <span className="meta-label">Seed</span>
              <code>{bestRun.seed ?? "N/A"}</code>
            </div>
            <div className="meta-item">
              <span className="meta-label">Timestamp</span>
              <code>{bestRun.timestamp}</code>
            </div>
            <div className="meta-item">
              <span className="meta-label">Packs Used</span>
              <code>{bestRun.packs_used.join(", ") || "N/A"}</code>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

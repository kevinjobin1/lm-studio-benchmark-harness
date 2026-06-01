import React from "react";
import { Bar } from "react-chartjs-2";
import type { BenchmarkResult, FailureBreakdown } from "../lib/loadResults";

interface FailureHeatmapProps {
  results: BenchmarkResult[];
}

const LABEL_MAP: Record<string, string> = {
  hallucinated_api: "Hallucinated API",
  wrong_async_usage: "Wrong Async",
  incorrect_json_schema: "Bad JSON",
  syntax_error: "Syntax Error",
  logic_error: "Logic Error",
  type_error: "Type Error",
  missing_import: "Missing Import",
  stale_closure: "Stale Closure",
  race_condition: "Race Condition",
  incorrect_di: "Bad DI",
  oververbose: "Oververbose",
  missed_constraint: "Missed Constraint",
  other: "Other",
};

export default function FailureHeatmap({ results }: FailureHeatmapProps) {
  if (results.length === 0) {
    return <div className="empty-state">No failure data available</div>;
  }

  const allKeys = Object.keys(results[0].failures);
  const activeKeys = allKeys.filter((k) =>
    results.some((r) => (r.failures as FailureBreakdown)[k] > 0),
  );

  if (activeKeys.length === 0) {
    return (
      <div className="empty-state success">
        <span className="check-icon">✓</span>
        No failures detected across any model
      </div>
    );
  }

  const labels = activeKeys.map((k) => LABEL_MAP[k] || k);

  const datasets = results.map((r, i) => {
    const hue = (i * 50 + 260) % 360;
    return {
      label: r.model,
      data: activeKeys.map(
        (k) => (r.failures as Record<string, number>)[k] || 0,
      ),
      backgroundColor: `hsla(${hue}, 60%, 55%, 0.7)`,
      borderColor: `hsla(${hue}, 60%, 55%, 1)`,
      borderWidth: 1,
      borderRadius: 4,
      borderSkipped: false,
    };
  });

  const data = { labels, datasets };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        grid: { color: "rgba(255,255,255,0.06)" },
        ticks: {
          color: "rgba(255,255,255,0.4)",
          font: { size: 11 },
          stepSize: 1,
        },
        title: {
          display: true,
          text: "Occurrences",
          color: "rgba(255,255,255,0.4)",
          font: { size: 11 },
        },
      },
      y: {
        grid: { display: false },
        ticks: {
          color: "rgba(255,255,255,0.6)",
          font: { size: 11 },
        },
      },
    },
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: {
          color: "rgba(255,255,255,0.6)",
          padding: 16,
          usePointStyle: true,
          font: { size: 12 },
        },
      },
      tooltip: {
        backgroundColor: "rgba(10,10,10,0.9)",
        padding: 12,
        borderColor: "rgba(255,255,255,0.1)",
        borderWidth: 1,
        callbacks: {
          label: (ctx: { dataset: { label?: string }; raw: unknown }) =>
            `${ctx.dataset.label}: ${ctx.raw} occurrence${(ctx.raw as number) !== 1 ? "s" : ""}`,
        },
      },
    },
  };

  return (
    <div className="heatmap-container">
      <div className="heatmap-inner">
        <Bar data={data} options={options} />
      </div>
    </div>
  );
}

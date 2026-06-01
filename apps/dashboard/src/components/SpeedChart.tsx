import React from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import type { ModelSummary } from "../lib/loadResults";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
);

interface SpeedChartProps {
  models: ModelSummary[];
}

const BAR_COLORS = [
  "rgba(147, 51, 234, 0.7)",
  "rgba(59, 130, 246, 0.7)",
  "rgba(16, 185, 129, 0.7)",
  "rgba(245, 158, 11, 0.7)",
  "rgba(239, 68, 68, 0.7)",
  "rgba(139, 92, 246, 0.7)",
];

export default function SpeedChart({ models }: SpeedChartProps) {
  const topModels = models.slice(0, 6);

  const data = {
    labels: topModels.map((m) => m.model),
    datasets: [
      {
        label: "tokens/sec",
        data: topModels.map((m) => m.performance.tokens_per_sec),
        backgroundColor: BAR_COLORS.slice(0, topModels.length),
        borderColor: BAR_COLORS.slice(0, topModels.length).map((c) =>
          c.replace("0.7", "1"),
        ),
        borderWidth: 1,
        borderRadius: 6,
        borderSkipped: false,
      },
      {
        label: "Normalized tok/s",
        data: topModels.map((m) => m.performance.normalized_tps),
        backgroundColor: BAR_COLORS.slice(0, topModels.length).map((c) =>
          c.replace("0.7", "0.25"),
        ),
        borderColor: BAR_COLORS.slice(0, topModels.length).map((c) =>
          c.replace("0.7", "0.5"),
        ),
        borderWidth: 1,
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: "y" as const,
    scales: {
      x: {
        grid: { color: "rgba(255,255,255,0.06)" },
        ticks: { color: "rgba(255,255,255,0.4)", font: { size: 11 } },
      },
      y: {
        grid: { display: false },
        ticks: {
          color: "rgba(255,255,255,0.6)",
          font: { size: 12 },
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
            `${ctx.dataset.label}: ${(ctx.raw as number).toFixed(1)} tok/s`,
        },
      },
    },
  };

  return (
    <div className="speed-chart-container">
      <div className="speed-chart-inner">
        <Bar data={data} options={options} />
      </div>
    </div>
  );
}

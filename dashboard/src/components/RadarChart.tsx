import React from 'react';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';
import type { ModelSummary } from '../lib/loadResults';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface RadarChartProps {
  models: ModelSummary[];
}

const CATEGORIES = ['Coding', 'Reasoning', 'Instructions', 'Frontend', 'Math', 'Debugging'] as const;
const CATEGORY_KEYS = ['coding_score', 'reasoning_score', 'instruction_score', 'frontend_score', 'math_score', 'debugging_score'] as const;

const MODEL_COLORS = [
  { bg: 'rgba(147, 51, 234, 0.15)', border: 'rgba(147, 51, 234, 0.8)' },
  { bg: 'rgba(59, 130, 246, 0.15)', border: 'rgba(59, 130, 246, 0.8)' },
  { bg: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.8)' },
  { bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.8)' },
  { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.8)' },
  { bg: 'rgba(139, 92, 246, 0.15)', border: 'rgba(139, 92, 246, 0.8)' },
];

export default function RadarChart({ models }: RadarChartProps) {
  const topModels = models.slice(0, 6);

  const data = {
    labels: CATEGORIES as unknown as string[],
    datasets: topModels.map((m, i) => ({
      label: m.model,
      data: CATEGORY_KEYS.map(k => (m.metrics as Record<string, number>)[k] || 0),
      backgroundColor: MODEL_COLORS[i]?.bg ?? 'rgba(100,100,100,0.15)',
      borderColor: MODEL_COLORS[i]?.border ?? 'rgba(100,100,100,0.8)',
      borderWidth: 2,
      pointBackgroundColor: MODEL_COLORS[i]?.border ?? 'rgba(100,100,100,0.8)',
      pointBorderColor: '#0a0a0a',
      pointBorderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 6,
    })),
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        beginAtZero: true,
        max: 1,
        min: 0,
        ticks: {
          stepSize: 0.2,
          display: true,
          color: 'rgba(255,255,255,0.35)',
          backdropColor: 'transparent',
          font: { size: 9 },
        },
        grid: {
          color: 'rgba(255,255,255,0.06)',
        },
        angleLines: {
          color: 'rgba(255,255,255,0.06)',
        },
        pointLabels: {
          color: 'rgba(255,255,255,0.6)',
          font: { size: 11, weight: '500' as const },
        },
      },
    },
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          color: 'rgba(255,255,255,0.6)',
          padding: 20,
          usePointStyle: true,
          pointStyleWidth: 8,
          font: { size: 12 },
        },
      },
      tooltip: {
        backgroundColor: 'rgba(10,10,10,0.9)',
        titleFont: { size: 13 },
        bodyFont: { size: 12 },
        padding: 12,
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        callbacks: {
          label: (ctx: { dataset: { label?: string }; raw: unknown }) =>
            `${ctx.dataset.label}: ${((ctx.raw as number) * 100).toFixed(0)}%`,
        },
      },
    },
  };

  return (
    <div className="radar-chart-container">
      <div className="radar-chart-inner">
        <Radar data={data} options={options} />
      </div>
    </div>
  );
}

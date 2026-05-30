import React from 'react';
import type { BenchmarkResult } from '../lib/loadResults';

interface ModelCardProps {
  result: BenchmarkResult;
  rank: number;
}

function getRankEmoji(rank: number): string {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return `#${rank}`;
}

function getTierLabel(overall: number): string {
  if (overall >= 0.90) return 'S-TIER';
  if (overall >= 0.80) return 'A-TIER';
  if (overall >= 0.65) return 'B-TIER';
  if (overall >= 0.50) return 'C-TIER';
  return 'F-TIER';
}

export default function ModelCard({ result, rank }: ModelCardProps) {
  const overallPct = (result.metrics.overall_score * 100).toFixed(1);
  const speedClass =
    result.performance.tokens_per_sec > 65 ? 'metric-good' :
    result.performance.tokens_per_sec > 45 ? 'metric-ok' : 'metric-slow';

  return (
    <article className={`model-card ${rank === 1 ? 'model-card-top' : ''}`}>
      <div className="model-card-header">
        <div className="model-card-rank">
          <span className="rank-emoji">{getRankEmoji(rank)}</span>
        </div>
        <div className="model-card-title">
          <h3 className="model-card-name">{result.model}</h3>
          <div style={{ display: 'flex', gap: 4, marginTop: 2, flexWrap: 'wrap' as const }}>
            {result.model_metadata.size && (
              <span className="chip chip-primary">{result.model_metadata.size}</span>
            )}
            {result.model_metadata.quantization && (
              <span className="chip chip-success">{result.model_metadata.quantization}</span>
            )}
            <span className="chip chip-warning">{getTierLabel(result.metrics.overall_score)}</span>
          </div>
        </div>
      </div>

      <a href={`/model/${encodeURIComponent(result.model)}`} className="model-card-overall">
        <span className="overall-label">Overall</span>
        <span className="overall-value">{overallPct}%</span>
      </a>

      <div className="model-card-metrics">
        <div className="metric-row">
          <span className="metric-label">Coding</span>
          <div className="metric-bar-track">
            <div
              className="metric-bar-fill"
              style={{ width: `${result.metrics.coding_score * 100}%` }}
            />
          </div>
          <span className="metric-val">{(result.metrics.coding_score * 100).toFixed(0)}%</span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Reasoning</span>
          <div className="metric-bar-track">
            <div
              className="metric-bar-fill"
              style={{ width: `${result.metrics.reasoning_score * 100}%` }}
            />
          </div>
          <span className="metric-val">{(result.metrics.reasoning_score * 100).toFixed(0)}%</span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Instructions</span>
          <div className="metric-bar-track">
            <div
              className="metric-bar-fill"
              style={{ width: `${result.metrics.instruction_score * 100}%` }}
            />
          </div>
          <span className="metric-val">{(result.metrics.instruction_score * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className="model-card-perf">
        <div className={`perf-badge ${speedClass}`}>
          <span className="perf-value">{result.performance.tokens_per_sec.toFixed(0)}</span>
          <span className="perf-unit">tok/s</span>
        </div>
        <div className="perf-badge">
          <span className="perf-value">{result.performance.ttft_ms.toFixed(0)}</span>
          <span className="perf-unit">ms TTFT</span>
        </div>
        <div className="perf-badge">
          <span className="perf-value">{result.stats.runs}</span>
          <span className="perf-unit">runs</span>
        </div>
      </div>

      <p className="model-card-personality">{result.stats.runs} runs &middot; CI [{result.stats.confidence_95 ? `${(result.stats.confidence_95[0] * 100).toFixed(1)}%, ${(result.stats.confidence_95[1] * 100).toFixed(1)}%` : 'N/A'}]</p>
    </article>
  );
}

import React, { useState, useMemo } from "react";
import type { ModelSummary } from "../lib/loadResults";

interface LeaderboardTableProps {
  models: ModelSummary[];
  loading?: boolean;
}

type SortKey = "overall" | "coding" | "throughput";

function getTier(overall: number): { label: string; cls: string } {
  if (overall >= 0.9) return { label: "S-TIER", cls: "tier-s" };
  if (overall >= 0.8) return { label: "A-TIER", cls: "tier-a" };
  if (overall >= 0.65) return { label: "B-TIER", cls: "tier-b" };
  if (overall >= 0.5) return { label: "C-TIER", cls: "tier-c" };
  return { label: "F-TIER", cls: "tier-f" };
}

function getRankMedal(index: number): { emoji: string; cls: string } {
  if (index === 0) return { emoji: "🥇", cls: "rank-gold" };
  if (index === 1) return { emoji: "🥈", cls: "rank-silver" };
  if (index === 2) return { emoji: "🥉", cls: "rank-bronze" };
  return { emoji: String(index + 1).padStart(2, "0"), cls: "" };
}

const SKELETON_ROWS = 5;

export default function LeaderboardTable({ models, loading }: LeaderboardTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("overall");

  const sorted = useMemo(() => {
    const arr = [...models];
    switch (sortKey) {
      case "coding":
        arr.sort((a, b) => b.metrics.coding_score - a.metrics.coding_score);
        break;
      case "throughput":
        arr.sort(
          (a, b) => b.performance.tokens_per_sec - a.performance.tokens_per_sec,
        );
        break;
      default:
        arr.sort((a, b) => b.metrics.overall_score - a.metrics.overall_score);
        break;
    }
    return arr;
  }, [models, sortKey]);

  if (loading) {
    return (
      <div className="leaderboard-table-wrapper">
        <div className="table-header">
          <h3>Rankings</h3>
          <div className="table-sort">
            <span className="sort-label">SORT BY:</span>
            <span className="skeleton-pulse" style={{ display: 'inline-block', width: 100, height: 14, borderRadius: 'var(--radius-sm)' }} />
          </div>
        </div>
        <table className="leaderboard-table">
          <thead>
            <tr>
              <th className="lb-th-rank">#</th>
              <th className="lb-th-model">Model</th>
              <th className="lb-th-bar">Overall</th>
              <th className="lb-th-score">Coding</th>
              <th className="lb-th-score">Speed</th>
              <th className="lb-th-tier">Tier</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
              <tr key={i}>
                <td className="lb-td-rank">
                  <span className="skeleton-pulse" style={{ display: 'inline-block', width: 20, height: 16, borderRadius: 'var(--radius-sm)' }} />
                </td>
                <td className="lb-td-model">
                  <div className="skeleton-row">
                    <div className="skeleton-pulse" style={{ width: 120, height: 14, borderRadius: 'var(--radius-sm)' }} />
                    <div className="skeleton-pulse" style={{ width: 40, height: 10, borderRadius: 'var(--radius-sm)', opacity: 0.5 }} />
                  </div>
                </td>
                <td className="lb-td-bar">
                  <div className="lb-bar-container">
                    <div className="skeleton-pulse" style={{ width: 50, height: 12, borderRadius: 'var(--radius-sm)' }} />
                    <div className="lb-bar-track">
                      <div
                        className="lb-bar-fill skeleton-pulse"
                        style={{ width: `${[85, 72, 60, 45, 30][i]}%`, background: 'var(--bg-bright)' }}
                      />
                    </div>
                  </div>
                </td>
                <td className="lb-td-score">
                  <span className="skeleton-pulse" style={{ display: 'inline-block', width: 40, height: 16, borderRadius: 'var(--radius-sm)' }} />
                </td>
                <td className="lb-td-speed">
                  <span className="skeleton-pulse" style={{ display: 'inline-block', width: 50, height: 14, borderRadius: 'var(--radius-sm)' }} />
                </td>
                <td className="lb-td-tier">
                  <span className="skeleton-pulse" style={{ display: 'inline-block', width: 56, height: 14, borderRadius: 'var(--radius-sm)' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="lb-footnote">
          <span className="skeleton-pulse" style={{ display: 'inline-block', width: 200, height: 12, borderRadius: 'var(--radius-sm)' }} />
        </div>
      </div>
    );
  }

  return (
    <div className="leaderboard-table-wrapper">
      {/* Sort controls */}
      <div className="table-header">
        <h3>Rankings</h3>
        <div className="table-sort">
          <span className="sort-label">SORT BY:</span>
          <label htmlFor="leaderboard-sort" className="sr-only">Sort by:</label>
          <select
            id="leaderboard-sort"
            className="sort-select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
          >
            <option value="overall">Overall Score</option>
            <option value="coding">Coding</option>
            <option value="throughput">Throughput</option>
          </select>
        </div>
      </div>

      <table className="leaderboard-table">
        <thead>
          <tr>
            <th className="lb-th-rank">#</th>
            <th className="lb-th-model">Model</th>
            <th className="lb-th-bar">Overall</th>
            <th className="lb-th-score">Coding</th>
            <th className="lb-th-score">Speed</th>
            <th className="lb-th-tier">Tier</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((m, i) => {
            const pct = m.metrics.overall_score * 100;
            const codeScore = m.metrics.coding_score * 100;
            const tier = getTier(m.metrics.overall_score);
            const medal = getRankMedal(i);
            const barColor =
              pct >= 80
                ? "var(--success)"
                : pct >= 60
                  ? "var(--brand-primary)"
                  : pct >= 40
                    ? "var(--warning)"
                    : "var(--error)";

            return (
              <tr key={m.model} className={i < 3 ? "lb-row-podium" : ""}>
                <td className="lb-td-rank">
                  <span className={`rank-medal ${medal.cls}`}>
                    {medal.emoji}
                  </span>
                </td>
                <td className="lb-td-model">
                  <div className="lb-model-cell">
                    <div className="lb-model-name-row">
                      <a
                        href={`/model/${encodeURIComponent(m.model)}`}
                        className="lb-model-link"
                      >
                        {m.model}
                      </a>
                      {m.trace_ids && m.trace_ids.length > 0 && (
                        <a
                          href={`/traces?trace_id=${encodeURIComponent(m.trace_ids[0])}`}
                          className="lb-trace-link"
                          title="View execution traces"
                        >
                          <span className="material-symbols-outlined lb-trace-icon">
                            account_tree
                          </span>
                        </a>
                      )}
                      {m.source === "community" && (
                        <span className="source-badge source-community" title="Community submission">
                          community
                        </span>
                      )}
                    </div>
                    <span className="lb-model-sub">
                      {m.metadata.size || "—"}
                      {m.metadata.quantization
                        ? ` · ${m.metadata.quantization}`
                        : ""}
                    </span>
                  </div>
                </td>
                <td className="lb-td-bar">
                  <div className="lb-bar-container">
                    <div className="lb-bar-label">{pct.toFixed(1)}%</div>
                    <div className="lb-bar-track">
                      <div
                        className="lb-bar-fill"
                        style={{ width: `${pct}%`, background: barColor }}
                      />
                    </div>
                  </div>
                </td>
                <td className="lb-td-score">
                  <span className="lb-score-chip">{codeScore.toFixed(1)}</span>
                </td>
                <td className="lb-td-speed">
                  <span className="lb-speed-value">
                    {m.performance.tokens_per_sec.toFixed(0)}
                  </span>
                  <span className="lb-speed-unit">tok/s</span>
                </td>
                <td className="lb-td-tier">
                  <span className={`tier-badge ${tier.cls}`}>{tier.label}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="lb-footnote">
        <span className="material-symbols-outlined lb-footnote-icon">
          sensors
        </span>
        <span className="lb-footnote-text">
          Benchmarks on Apple Silicon · {models.length} models · sorted by{" "}
          {sortKey === "overall"
            ? "overall score"
            : sortKey === "coding"
              ? "coding score"
              : "throughput"}
        </span>
      </div>
    </div>
  );
}

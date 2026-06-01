import React, { useState, useMemo } from "react";
import type { ModelSummary } from "../lib/loadResults";

interface LeaderboardTableProps {
  models: ModelSummary[];
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

export default function LeaderboardTable({ models }: LeaderboardTableProps) {
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

  return (
    <div className="leaderboard-table-wrapper">
      {/* Sort controls */}
      <div className="table-header">
        <h3>Rankings</h3>
        <div className="table-sort">
          <span className="sort-label">SORT BY:</span>
          <select
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
                    <a
                      href={`/model/${encodeURIComponent(m.model)}`}
                      className="lb-model-link"
                    >
                      {m.model}
                    </a>
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

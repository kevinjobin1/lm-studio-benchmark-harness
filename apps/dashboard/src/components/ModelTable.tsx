import React from "react";
import type { ModelSummary } from "../lib/loadResults";

interface ModelTableProps {
  models: ModelSummary[];
}

// Simplified category set matching the target design
const CATEGORIES = [
  { key: "coding_score", label: "Coding" },
  { key: "reasoning_score", label: "Reasoning" },
  { key: "instruction_score", label: "Instruct" },
] as const;

function getTier(overall: number): { label: string; cls: string } {
  if (overall >= 0.9) return { label: "S-TIER", cls: "tier-s" };
  if (overall >= 0.8) return { label: "A-TIER", cls: "tier-a" };
  if (overall >= 0.65) return { label: "B-TIER", cls: "tier-b" };
  if (overall >= 0.5) return { label: "C-TIER", cls: "tier-c" };
  return { label: "F-TIER", cls: "tier-f" };
}

export default function ModelTable({ models }: ModelTableProps) {
  // Sort by overall score descending (matches target design)
  const sorted = [...models].sort(
    (a, b) => b.metrics.overall_score - a.metrics.overall_score,
  );

  return (
    <div className="model-table-wrapper">
      <table className="model-table">
        <thead>
          <tr>
            <th className="th-model">Model</th>
            {CATEGORIES.map((c) => (
              <th key={c.key} className="th-score">
                {c.label}
              </th>
            ))}
            <th className="th-score">Tok/s</th>
            <th className="th-overall">Overall</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((m, i) => {
            const codeScore =
              (m.metrics as Record<string, number>)["coding_score"] || 0;
            const reasoningScore =
              (m.metrics as Record<string, number>)["reasoning_score"] || 0;
            const instructScore =
              (m.metrics as Record<string, number>)["instruction_score"] || 0;
            const tier = getTier(m.metrics.overall_score);

            return (
              <tr key={m.model} className={i === 0 ? "row-top" : ""}>
                <td className="td-model">
                  <div className="model-cell">
                    <a
                      href={`/model/${encodeURIComponent(m.model)}`}
                      className="model-link"
                    >
                      {m.model}
                    </a>
                    <span className="model-sub">
                      {m.metadata.size || "—"}{" "}
                      {m.metadata.quantization
                        ? `· ${m.metadata.quantization}`
                        : ""}
                    </span>
                  </div>
                </td>
                <td className="td-score">
                  <span className="score-chip">
                    {(codeScore * 100).toFixed(1)}
                  </span>
                </td>
                <td className="td-score">
                  <span className="score-chip score-chip-secondary">
                    {(reasoningScore * 100).toFixed(1)}
                  </span>
                </td>
                <td className="td-score">
                  <span className="score-chip score-chip-secondary">
                    {(instructScore * 100).toFixed(1)}
                  </span>
                </td>
                <td className="td-score mono-data">
                  {m.performance.tokens_per_sec.toFixed(1)}
                </td>
                <td className="td-overall">
                  <div className="overall-cell">
                    <span className="overall-value">
                      {(m.metrics.overall_score * 100).toFixed(1)}
                    </span>
                    <span className={`tier-badge ${tier.cls}`}>
                      {tier.label}
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

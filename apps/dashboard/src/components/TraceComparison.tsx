import React from "react";
import type { TraceRun, TraceStep } from "../lib/traceTypes";
import { stepIcons, stepColors } from "../lib/traceTypes";

// ── Props ──────────────────────────────────────────────────────────

interface TraceComparisonProps {
  /** Primary model traces (left column). If empty, shows empty state. */
  tracesA: TraceRun[];
  /** Secondary model traces (right column). */
  tracesB: TraceRun[];
  /** Optional third model traces (shown in a third column). */
  tracesC?: TraceRun[];
  /** Show per-step timing deltas between models. Default: true. */
  showDiffs?: boolean;
}

// ── Status icon map ─────────────────────────────────────────────

const statusIcon: Record<string, string> = {
  completed: "check_circle",
  failed: "cancel",
  running: "sync",
};

// ── Helpers ────────────────────────────────────────────────────────

/**
 * Pick the most interesting trace from a list: prefer the most recent
 * completed trace with the most steps.
 */
function pickBestTrace(traces: TraceRun[]): TraceRun | null {
  if (traces.length === 0) return null;

  const completed = traces.filter((t) => t.status === "completed");
  if (completed.length > 0) {
    return completed.reduce((a, b) =>
      a.steps.length >= b.steps.length ? a : b,
    );
  }
  return traces[0];
}

/**
 * Compute a diff summary between two trace runs.
 * Returns human-readable comparison strings.
 */
function computeDiff(a: TraceRun | null, b: TraceRun | null) {
  if (!a || !b) return null;

  const timeDelta = b.totalTimeMs - a.totalTimeMs;
  const stepDelta = b.steps.length - a.steps.length;
  const faster = timeDelta > 0 ? a.model : b.model;
  const slower = timeDelta > 0 ? b.model : a.model;
  const deltaMs = Math.abs(timeDelta);

  return {
    timeDeltaMs: deltaMs,
    fasterModel: timeDelta > 0 ? a.model : b.model,
    slowerModel: timeDelta > 0 ? b.model : a.model,
    timeSummary: `${faster} was ${deltaMs}ms faster than ${slower}`,
    stepDelta,
    stepSummary:
      stepDelta === 0
        ? "Same number of steps"
        : stepDelta > 0
          ? `${b.model} used ${stepDelta} more step${stepDelta > 1 ? "s" : ""}`
          : `${a.model} used ${Math.abs(stepDelta)} more step${Math.abs(stepDelta) > 1 ? "s" : ""}`,
  };
}

/**
 * Compute max steps across both traces for row alignment.
 */
function maxSteps(a: TraceRun | null, b: TraceRun | null): number {
  const aSteps = a?.steps.length ?? 0;
  const bSteps = b?.steps.length ?? 0;
  return Math.max(aSteps, bSteps);
}

/**
 * Per-step timing delta between two aligned steps.
 * Returns `null` if either step is missing or diff mode is off.
 */
interface StepDelta {
  /** Signed timing delta (thisStepsMs - otherStepsMs). Negative = faster. */
  deltaMs: number;
  /** "faster" | "slower" | "equal" */
  verdict: "faster" | "slower" | "equal";
}

function computeStepDelta(
  thisStep: TraceStep | undefined,
  otherStep: TraceStep | undefined,
): StepDelta | null {
  if (!thisStep || !otherStep) return null;
  const delta = thisStep.timing_ms - otherStep.timing_ms;
  if (delta === 0) return { deltaMs: 0, verdict: "equal" };
  return {
    deltaMs: delta,
    verdict: delta < 0 ? "faster" : "slower",
  };
}

// ── Diff Badge ─────────────────────────────────────────────────────

function DiffBadge({ delta }: { delta: StepDelta }) {
  const absMs = Math.abs(delta.deltaMs);
  if (delta.verdict === "equal") {
    return (
      <span className="tcmp-delta tcmp-delta-equal" title="Same timing">
        ={absMs}ms
      </span>
    );
  }
  return (
    <span
      className={`tcmp-delta tcmp-delta-${delta.verdict}`}
      title={`${delta.verdict === "faster" ? "Faster" : "Slower"} by ${absMs}ms`}
    >
      {delta.verdict === "faster" ? <>&minus;{absMs}ms</> : <>+{absMs}ms</>}
    </span>
  );
}

// ── Step Row ───────────────────────────────────────────────────────

function StepCell({
  step,
  model,
  delta,
  showDiffs,
}: {
  step?: TraceStep;
  model: string;
  delta?: StepDelta | null;
  showDiffs?: boolean;
}) {
  if (!step) {
    return (
      <div className="tcmp-cell tcmp-cell-empty">
        <span className="tcmp-empty-label">—</span>
      </div>
    );
  }

  const color = stepColors[step.type] || "var(--text-tertiary)";
  const icon = stepIcons[step.type] || "circle";

  return (
    <div className="tcmp-cell">
      <div className="tcmp-cell-header">
        <span
          className="material-symbols-outlined tcmp-step-icon"
          style={{ color }}
        >
          {icon}
        </span>
        <span
          className="tcmp-type-chip"
          style={{
            background: `${color}15`,
            color,
            borderColor: `${color}30`,
          }}
        >
          {step.type.replace("_", " ")}
        </span>
        <span className="tcmp-cell-time">{step.timing_ms}ms</span>
        {showDiffs && delta && <DiffBadge delta={delta} />}
      </div>
      <div className="tcmp-cell-label">{step.label}</div>
      {step.detail && <div className="tcmp-cell-detail">{step.detail}</div>}
      {step.status === "failure" && (
        <span
          className="material-symbols-outlined tcmp-fail-icon"
          style={{ color: "var(--error)" }}
        >
          error
        </span>
      )}
    </div>
  );
}

// ── Empty State ────────────────────────────────────────────────────

function EmptyComparison() {
  return (
    <div className="tcmp-empty">
      <span
        className="material-symbols-outlined"
        style={{ fontSize: 40, color: "var(--text-tertiary)", marginBottom: 12 }}
      >
        compare_arrows
      </span>
      <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>
        No trace data available for comparison.
        <br />
        Run benchmarks with trace capture enabled to populate this view.
      </p>
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────

export default function TraceComparison({
  tracesA,
  tracesB,
  tracesC,
  showDiffs = true,
}: TraceComparisonProps) {
  const bestA = pickBestTrace(tracesA);
  const bestB = pickBestTrace(tracesB);
  const bestC = tracesC ? pickBestTrace(tracesC) : null;

  // Both traces needed for meaningful comparison
  if (!bestA && !bestB) return <EmptyComparison />;

  const diff = computeDiff(bestA, bestB);
  const maxStepCount = maxSteps(bestA, bestB);
  const columns = bestC ? 3 : 2;

  return (
    <div className="tcmp-root">
      {/* ── Diff Summary Bar ──────────────────────────────────── */}
      {diff && (
        <div className="tcmp-diff-bar">
          <div className="tcmp-diff-item">
            <span className="material-symbols-outlined tcmp-diff-icon">
              schedule
            </span>
            <span className="tcmp-diff-text">{diff.timeSummary}</span>
          </div>
          <div className="tcmp-diff-divider" />
          <div className="tcmp-diff-item">
            <span className="material-symbols-outlined tcmp-diff-icon">
              stairs
            </span>
            <span className="tcmp-diff-text">{diff.stepSummary}</span>
          </div>
          <div className="tcmp-diff-divider" />
          <div className="tcmp-diff-item">
            <span className="material-symbols-outlined tcmp-diff-icon">
              speed
            </span>
            <span className="tcmp-diff-text">
              {diff.timeDeltaMs > 0
                ? `${diff.fasterModel} leads by ${diff.timeDeltaMs}ms`
                : "Identical total time"}
            </span>
          </div>
          {showDiffs && (
            <>
              <div className="tcmp-diff-divider" />
              <div className="tcmp-diff-item">
                <span className="material-symbols-outlined tcmp-diff-icon" style={{ color: "var(--success)" }}>
                  trending_down
                </span>
                <span className="tcmp-diff-text" style={{ color: "var(--success)" }}>
                  Green = faster step
                </span>
              </div>
              <div className="tcmp-diff-divider" />
              <div className="tcmp-diff-item">
                <span className="material-symbols-outlined tcmp-diff-icon" style={{ color: "var(--error)" }}>
                  trending_up
                </span>
                <span className="tcmp-diff-text" style={{ color: "var(--error)" }}>
                  Red = slower step
                </span>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Column Headers ────────────────────────────────────── */}
      <div
        className="tcmp-columns"
        style={{
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
        }}
      >
        {/* Model A */}
        <div className="tcmp-column">
          {bestA ? (
            <>
              <div className="tcmp-col-header">
                <span
                  className={`material-symbols-outlined tcmp-status-icon tcmp-status-${bestA.status}`}
                >
                  {statusIcon[bestA.status] || "help"}
                </span>
                <div>
                  <div className="tcmp-col-model">{bestA.model}</div>
                  <div className="tcmp-col-meta">
                    {bestA.pack} · {bestA.totalTimeMs}ms ·{" "}
                    {bestA.steps.length} steps
                  </div>
                </div>
              </div>
              <div className="tcmp-col-steps">
                {Array.from({ length: maxStepCount }, (_, i) => {
                  const stepA = bestA.steps[i];
                  const stepB = bestB?.steps[i];
                  const delta = showDiffs
                    ? computeStepDelta(stepA, stepB)
                    : null;
                  return (
                    <StepCell
                      key={i}
                      step={stepA}
                      model={bestA.model}
                      delta={delta}
                      showDiffs={showDiffs}
                    />
                  );
                })}
              </div>
            </>
          ) : (
            <div className="tcmp-col-header tcmp-col-none">
              <span style={{ color: "var(--text-tertiary)", fontSize: 13 }}>
                No traces available
              </span>
            </div>
          )}
        </div>

        {/* Model B */}
        <div className="tcmp-column">
          {bestB ? (
            <>
              <div className="tcmp-col-header">
                <span
                  className={`material-symbols-outlined tcmp-status-icon tcmp-status-${bestB.status}`}
                >
                  {statusIcon[bestB.status] || "help"}
                </span>
                <div>
                  <div className="tcmp-col-model">{bestB.model}</div>
                  <div className="tcmp-col-meta">
                    {bestB.pack} · {bestB.totalTimeMs}ms ·{" "}
                    {bestB.steps.length} steps
                  </div>
                </div>
              </div>
              <div className="tcmp-col-steps">
                {Array.from({ length: maxStepCount }, (_, i) => {
                  const stepB = bestB.steps[i];
                  const stepA = bestA?.steps[i];
                  const delta = showDiffs
                    ? computeStepDelta(stepB, stepA)
                    : null;
                  return (
                    <StepCell
                      key={i}
                      step={stepB}
                      model={bestB.model}
                      delta={delta}
                      showDiffs={showDiffs}
                    />
                  );
                })}
              </div>
            </>
          ) : (
            <div className="tcmp-col-header tcmp-col-none">
              <span style={{ color: "var(--text-tertiary)", fontSize: 13 }}>
                No traces available
              </span>
            </div>
          )}
        </div>

        {/* Optional Model C */}
        {bestC !== null && (
          <div className="tcmp-column">
            {bestC ? (
              <>
                <div className="tcmp-col-header">
                  <span
                    className={`material-symbols-outlined tcmp-status-icon tcmp-status-${bestC.status}`}
                  >
                    {statusIcon[bestC.status] || "help"}
                  </span>
                  <div>
                    <div className="tcmp-col-model">{bestC.model}</div>
                    <div className="tcmp-col-meta">
                      {bestC.pack} · {bestC.totalTimeMs}ms ·{" "}
                      {bestC.steps.length} steps
                    </div>
                  </div>
                </div>
                <div className="tcmp-col-steps">
                  {Array.from({ length: maxStepCount }, (_, i) => (
                    <StepCell
                      key={i}
                      step={bestC.steps[i]}
                      model={bestC.model}
                      showDiffs={false}
                    />
                  ))}
                </div>
              </>
            ) : (
              <div className="tcmp-col-header tcmp-col-none">
                <span style={{ color: "var(--text-tertiary)", fontSize: 13 }}>
                  No traces available
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Legend ─────────────────────────────────────────────── */}
      <div className="tcmp-legend">
        <span className="tcmp-legend-label">Step types:</span>
        {Object.entries(stepIcons)
          .slice(0, 7)
          .map(([type, icon]) => (
            <span key={type} className="tcmp-legend-chip">
              <span
                className="material-symbols-outlined"
                style={{
                  fontSize: 12,
                  color: stepColors[type] || "var(--text-tertiary)",
                }}
              >
                {icon}
              </span>
              <span style={{ fontSize: 10 }}>{type.replace("_", " ")}</span>
            </span>
          ))}
        {showDiffs && (
          <>
            <span className="tcmp-legend-divider">|</span>
            <span className="tcmp-legend-label">Diffs:</span>
            <span className="tcmp-legend-chip">
              <span className="tcmp-delta-dot tcmp-dot-faster" />
              <span style={{ fontSize: 10, color: "var(--success)" }}>
                faster
              </span>
            </span>
            <span className="tcmp-legend-chip">
              <span className="tcmp-delta-dot tcmp-dot-slower" />
              <span style={{ fontSize: 10, color: "var(--error)" }}>
                slower
              </span>
            </span>
          </>
        )}
      </div>
    </div>
  );
}

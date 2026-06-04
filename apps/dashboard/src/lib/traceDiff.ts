/**
 * Trace diff types and loaders for the dashboard comparison system.
 *
 * Mirrors the Python ``core/trace_diff.py`` output so the dashboard
 * can render structured diff data from ``diff_traces()``.
 */

// ── Step-level diff ───────────────────────────────────────────────

export interface StepTextDiffOp {
  type: "equal" | "replace" | "delete" | "insert";
  text: string | { old: string; new: string };
}

export interface StepDiffEntry {
  index: number;
  diff_type: "match" | "modified" | "added" | "removed";
  type_a?: string | null;
  type_b?: string | null;
  label_a?: string | null;
  label_b?: string | null;
  timing_a_ms?: number | null;
  timing_b_ms?: number | null;
  timing_delta_ms?: number | null;
  status_a?: string | null;
  status_b?: string | null;
  text_diff?: StepTextDiffOp[];
}

// ── Metric-level diff ─────────────────────────────────────────────

export interface MetricDelta {
  a: number | null;
  b: number | null;
  delta: number | null;
  delta_pct?: number | null;
}

export interface MetricDiff {
  [metricName: string]: MetricDelta;
}

// ── Artifact-level diff ───────────────────────────────────────────

export interface TextDiffResult {
  operations: StepTextDiffOp[];
  stats: {
    insertions: number;
    deletions: number;
    replacements: number;
    equal_tokens: number;
    ratio: number;
  };
}

export interface ArtifactDiff {
  response_diff?: TextDiffResult;
  log_delta?: number;
  log_details?: { a: string[]; b: string[] };
  error_delta?: number;
  error_details?: { a: string[]; b: string[] };
}

// ── Summary ────────────────────────────────────────────────────────

export interface DiffTimingSummary {
  a_ms: number;
  b_ms: number;
  delta_ms: number;
  faster_model: string;
  summary: string;
}

export interface DiffTokenSummary {
  a: number;
  b: number;
  delta: number;
}

export interface DiffMemorySummary {
  a_mb: number;
  b_mb: number;
  delta_mb: number;
  summary: string;
}

export interface DiffSummary {
  models: { a: string; b: string };
  total_steps: number;
  step_matches: number;
  step_modified: number;
  step_added: number;
  step_removed: number;
  timing: DiffTimingSummary;
  tokens: DiffTokenSummary;
  memory: DiffMemorySummary;
}

// ── Full diff result ──────────────────────────────────────────────

export interface TraceDiffResult {
  summary: DiffSummary;
  steps: StepDiffEntry[];
  metrics: MetricDiff;
  artifacts: ArtifactDiff;
}

// ── Dashboard compute function (client-side fallback) ──────────────

import type { TraceRun } from "./traceTypes";

export interface SimpleStepDiff {
  index: number;
  label: string;
  type: string;
  timingDeltaMs: number;
  diffType: "match" | "modified" | "added" | "removed";
}

export interface SimpleTraceDiff {
  timingDeltaMs: number;
  stepDiffs: SimpleStepDiff[];
}

/**
 * Compute a lightweight step diff between two TraceRun objects.
 *
 * Used on the dashboard when the Python diff engine is unavailable
 * (e.g. browser runtime). For full token-level diffs, load via the
 * /api/traces/diff endpoint which calls the Python engine.
 */
export function computeTraceDiff(
  traceA: TraceRun,
  traceB: TraceRun,
): SimpleTraceDiff {
  const timingDeltaMs = traceB.totalTimeMs - traceA.totalTimeMs;
  const maxSteps = Math.max(traceA.steps.length, traceB.steps.length);
  const stepDiffs: SimpleStepDiff[] = [];

  for (let i = 0; i < maxSteps; i++) {
    const stepA = traceA.steps[i];
    const stepB = traceB.steps[i];

    if (!stepA && stepB) {
      stepDiffs.push({
        index: i,
        label: stepB.label,
        type: stepB.type,
        timingDeltaMs: stepB.timing_ms,
        diffType: "added",
      });
    } else if (stepA && !stepB) {
      stepDiffs.push({
        index: i,
        label: stepA.label,
        type: stepA.type,
        timingDeltaMs: -stepA.timing_ms,
        diffType: "removed",
      });
    } else if (stepA && stepB) {
      const delta = stepB.timing_ms - stepA.timing_ms;
      const isModified =
        stepA.type !== stepB.type ||
        stepA.label !== stepB.label ||
        Math.abs(delta) > 1;
      stepDiffs.push({
        index: i,
        label: stepB.label,
        type: stepB.type,
        timingDeltaMs: delta,
        diffType: isModified ? "modified" : "match",
      });
    }
  }

  return { timingDeltaMs, stepDiffs };
}

// ── API loader ────────────────────────────────────────────────────

/**
 * Load a structured trace diff from the Python engine via the dashboard API.
 *
 * Falls back to client-side ``computeTraceDiff()`` if the API is unavailable.
 */
export async function loadTraceDiff(
  traceIdA: string,
  traceIdB: string,
): Promise<TraceDiffResult | SimpleTraceDiff> {
  try {
    const resp = await fetch(
      `/api/traces/diff?trace_id_a=${encodeURIComponent(traceIdA)}&trace_id_b=${encodeURIComponent(traceIdB)}`,
    );
    if (resp.ok) {
      return (await resp.json()) as TraceDiffResult;
    }
  } catch {
    // API unavailable — fall through to client-side fallback
  }

  // Fallback: load both traces and compute a simple diff on the client
  try {
    const { loadTrace, mapTraceToRun } = await import("./loadTraces");
    const [dataA, dataB] = await Promise.all([
      loadTrace(traceIdA),
      loadTrace(traceIdB),
    ]);
    if (dataA && dataB) {
      const traceA = mapTraceToRun(dataA);
      const traceB = mapTraceToRun(dataB);
      return computeTraceDiff(traceA, traceB);
    }
  } catch {
    // Both fallbacks failed — return empty diff
  }

  return {
    timingDeltaMs: 0,
    stepDiffs: [],
  };
}

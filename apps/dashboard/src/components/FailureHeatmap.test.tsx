// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import FailureHeatmap from "./FailureHeatmap";
import type { BenchmarkResult } from "../lib/loadResults";

function makeResult(
  id: string,
  failures: Partial<BenchmarkResult["failures"]>,
): BenchmarkResult {
  const defaultFailures: BenchmarkResult["failures"] = {
    hallucinated_api: 0,
    wrong_async_usage: 0,
    incorrect_json_schema: 0,
    syntax_error: 0,
    logic_error: 0,
    type_error: 0,
    missing_import: 0,
    stale_closure: 0,
    race_condition: 0,
    incorrect_di: 0,
    oververbose: 0,
    missed_constraint: 0,
    other: 0,
  };
  return {
    run_id: `run-${id}`,
    model: `model-${id}`,
    model_metadata: { size: "7B" },
    hardware: { platform: "macOS", processor: "M3", memory_gb: 18, architecture: "arm64" },
    timestamp: "2026-06-02T02:25:52.205Z",
    git_sha: "abc1234",
    git_branch: "main",
    metrics: {
      coding_score: 0.8,
      reasoning_score: 0.75,
      instruction_score: 0.85,
      frontend_score: 0.7,
      math_score: 0.7,
      debugging_score: 0.65,
      overall_score: 0.78,
    },
    performance: {
      tokens_per_sec: 60,
      normalized_tps: 57,
      ttft_ms: 400,
      total_latency_ms: 3000,
      memory_pressure_mb: 1400,
    },
    stats: { mean: 0.78, std: 0.05, min: 0.73, max: 0.83, median: 0.78, runs: 5, confidence_95: null, coefficient_of_variation: 0.06 },
    failures: { ...defaultFailures, ...failures } as BenchmarkResult["failures"],
    category_scores: {},
    config_snapshot: {},
    prompt_version: "v1",
    packs_used: [],
    seed: null,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FailureHeatmap", () => {
  it('shows empty state when results array is empty', () => {
    render(<FailureHeatmap results={[]} />);
    expect(screen.getByText("No failure data available")).toBeTruthy();
  });

  it('shows "No failures detected" when all failure counts are zero', () => {
    const results = [makeResult("alpha", {})];
    render(<FailureHeatmap results={results} />);
    expect(screen.getByText("No failures detected across any model")).toBeTruthy();
  });

  it('shows check icon when no failures', () => {
    const results = [makeResult("alpha", {})];
    const { container } = render(<FailureHeatmap results={results} />);
    expect(container.querySelector(".check-icon")).toBeTruthy();
  });

  it("renders the chart container when there are failures", () => {
    const results = [makeResult("alpha", { syntax_error: 3, logic_error: 2 })];
    const { container } = render(<FailureHeatmap results={results} />);
    expect(container.querySelector(".heatmap-container")).toBeTruthy();
  });

  it("renders a canvas element via chart.js", () => {
    const results = [makeResult("alpha", { syntax_error: 3 })];
    const { container } = render(<FailureHeatmap results={results} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeTruthy();
  });

  it("renders the heatmap-inner div", () => {
    const results = [makeResult("alpha", { syntax_error: 3 })];
    const { container } = render(<FailureHeatmap results={results} />);
    expect(container.querySelector(".heatmap-inner")).toBeTruthy();
  });

  it("renders multiple models with different failures", () => {
    const results = [
      makeResult("alpha", { syntax_error: 3, logic_error: 2 }),
      makeResult("beta", { syntax_error: 1, stale_closure: 4 }),
    ];
    const { container } = render(<FailureHeatmap results={results} />);
    expect(container.querySelector(".heatmap-container")).toBeTruthy();
    expect(container.querySelector("canvas")).toBeTruthy();
  });

  it("does not render empty state when there are failures with non-zero values", () => {
    const results = [makeResult("alpha", { syntax_error: 1 })];
    render(<FailureHeatmap results={results} />);
    expect(screen.queryByText("No failure data available")).toBeNull();
    expect(screen.queryByText("No failures detected")).toBeNull();
  });

  it("shows empty state for results with only zero-count failures", () => {
    const results = [
      makeResult("alpha", { syntax_error: 0 }),
      makeResult("beta", { syntax_error: 0 }),
    ];
    render(<FailureHeatmap results={results} />);
    // All active keys have zero counts, so it should show "No failures detected"
    expect(screen.getByText("No failures detected across any model")).toBeTruthy();
  });
});

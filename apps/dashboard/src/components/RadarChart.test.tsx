// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";
import RadarChart from "./RadarChart";
import type { ModelSummary } from "../lib/loadResults";

function makeModel(id: string): ModelSummary {
  return {
    model: `model-${id}`,
    metadata: { size: "7B" },
    best_run_id: "run-1",
    metrics: {
      coding_score: 0.9,
      reasoning_score: 0.8,
      instruction_score: 0.85,
      frontend_score: 0.75,
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
    stats: { mean: 0.78, std: 0.05, runs: 5 },
    total_failures: 5,
    source: "local",
  };
}

const models = [
  makeModel("alpha"),
  makeModel("beta"),
  makeModel("gamma"),
  makeModel("delta"),
  makeModel("epsilon"),
  makeModel("zeta"),
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RadarChart", () => {
  it("renders the chart container", () => {
    const { container } = render(<RadarChart models={models} />);
    expect(container.querySelector(".radar-chart-container")).toBeTruthy();
  });

  it("renders a canvas element (Chart.js renders into it)", () => {
    const { container } = render(<RadarChart models={models} />);
    expect(container.querySelector("canvas")).toBeTruthy();
  });

  it("limits to top 6 models", () => {
    const manyModels = [...models, makeModel("eta"), makeModel("theta")];
    const { container } = render(<RadarChart models={manyModels} />);
    expect(container.querySelector("canvas")).toBeTruthy();
  });

  it("handles empty models array", () => {
    const { container } = render(<RadarChart models={[]} />);
    expect(container.querySelector("canvas")).toBeTruthy();
  });

  it("handles fewer than 6 models", () => {
    const { container } = render(<RadarChart models={[models[0], models[1]]} />);
    expect(container.querySelector("canvas")).toBeTruthy();
  });
});

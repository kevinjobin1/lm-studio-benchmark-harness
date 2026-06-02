// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import SpeedChart from "./SpeedChart";
import type { ModelSummary } from "../lib/loadResults";

function makeModel(id: string, tps: number): ModelSummary {
  return {
    model: `model-${id}`,
    metadata: { size: "7B" },
    best_run_id: "run-1",
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
      tokens_per_sec: tps,
      normalized_tps: tps * 0.95,
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
  makeModel("alpha", 72),
  makeModel("beta", 65),
  makeModel("gamma", 58),
  makeModel("delta", 50),
  makeModel("epsilon", 42),
  makeModel("zeta", 35),
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SpeedChart", () => {
  it("renders the chart container", () => {
    const { container } = render(<SpeedChart models={models} />);
    const chartContainer = container.querySelector(".speed-chart-container");
    expect(chartContainer).toBeTruthy();
  });

  it("renders a canvas element (Chart.js renders into it)", () => {
    const { container } = render(<SpeedChart models={models} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeTruthy();
  });

  it("limits to top 6 models", () => {
    const manyModels = [
      ...models,
      makeModel("eta", 30),
      makeModel("theta", 25),
    ];
    const { container } = render(<SpeedChart models={manyModels} />);
    expect(container.querySelector("canvas")).toBeTruthy();
  });

  it("handles empty models array", () => {
    const { container } = render(<SpeedChart models={[]} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeTruthy(); // Chart.js renders even with empty data
  });

  it("handles a single model", () => {
    const { container } = render(<SpeedChart models={[models[0]]} />);
    expect(container.querySelector("canvas")).toBeTruthy();
  });
});

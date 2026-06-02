// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ModelCard from "./ModelCard";
import type { BenchmarkResult } from "../lib/loadResults";

function makeResult(id: string, overall: number, tps: number): BenchmarkResult {
  return {
    run_id: `run-${id}`,
    model: `model-${id}`,
    model_metadata: { size: "7B", quantization: "Q4_K_M" },
    hardware: {
      platform: "macOS 15.6.1",
      processor: "Apple M3 Pro",
      memory_gb: 18,
      architecture: "arm64",
    },
    timestamp: "2026-06-02T02:25:52.205Z",
    git_sha: "abc1234",
    git_branch: "main",
    metrics: {
      coding_score: overall * 0.9,
      reasoning_score: overall * 0.85,
      instruction_score: overall * 0.95,
      frontend_score: overall * 0.8,
      math_score: overall * 0.75,
      debugging_score: overall * 0.7,
      overall_score: overall,
    },
    performance: {
      tokens_per_sec: tps,
      normalized_tps: tps * 0.95,
      ttft_ms: 420,
      total_latency_ms: 3000,
      memory_pressure_mb: 1400,
    },
    stats: {
      mean: overall,
      std: 0.05,
      min: overall - 0.05,
      max: overall + 0.05,
      median: overall,
      runs: 5,
      confidence_95: [overall - 0.03, overall + 0.03],
      coefficient_of_variation: 0.06,
    },
    failures: {
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
    },
    category_scores: {},
    config_snapshot: { temperature: 0.2 },
    prompt_version: "v1",
    packs_used: ["nestjs-pack"],
    seed: 42,
  };
}

const topResult = makeResult("alpha", 0.92, 72);
const secondResult = makeResult("beta", 0.75, 55);
const thirdResult = makeResult("gamma", 0.55, 38);

describe("ModelCard", () => {
  it("renders the model name", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("model-alpha")).toBeTruthy();
  });

  it("shows gold medal emoji for rank 1", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("🥇")).toBeTruthy();
  });

  it("shows silver medal emoji for rank 2", () => {
    render(<ModelCard result={secondResult} rank={2} />);
    expect(screen.getByText("🥈")).toBeTruthy();
  });

  it("shows bronze medal emoji for rank 3", () => {
    render(<ModelCard result={thirdResult} rank={3} />);
    expect(screen.getByText("🥉")).toBeTruthy();
  });

  it("shows numeric rank for ranks beyond 3", () => {
    render(<ModelCard result={topResult} rank={4} />);
    expect(screen.getByText("#4")).toBeTruthy();
  });

  it("renders the overall score as a percentage", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("92.0%")).toBeTruthy();
  });

  it("renders the correct tier label for S-tier", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("S-TIER")).toBeTruthy();
  });

  it("renders the correct tier label for B-tier", () => {
    render(<ModelCard result={secondResult} rank={2} />);
    expect(screen.getByText("B-TIER")).toBeTruthy();
  });

  it("renders the correct tier label for C-tier", () => {
    render(<ModelCard result={thirdResult} rank={3} />);
    expect(screen.getByText("C-TIER")).toBeTruthy();
  });

  it("renders metadata size and quantization chips", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("7B")).toBeTruthy();
    expect(screen.getByText("Q4_K_M")).toBeTruthy();
  });

  it("renders metric scores with percentages", () => {
    render(<ModelCard result={topResult} rank={1} />);
    // coding = 0.92 * 0.9 = 0.828 → 83%
    expect(screen.getByText("83%")).toBeTruthy();
  });

  it("renders tokens per second badge", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("72")).toBeTruthy();
    expect(screen.getByText("tok/s")).toBeTruthy();
  });

  it("renders ttft badge", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("420")).toBeTruthy();
    expect(screen.getByText("ms TTFT")).toBeTruthy();
  });

  it("renders runs count badge", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("runs")).toBeTruthy();
  });

  it("renders the confidence interval text", () => {
    render(<ModelCard result={topResult} rank={1} />);
    expect(screen.getByText(/89\.0%.*95\.0%/)).toBeTruthy();
  });

  it("renders a link to the model detail page", () => {
    render(<ModelCard result={topResult} rank={1} />);
    const link = screen.getByText("92.0%").closest("a");
    expect(link?.getAttribute("href")).toBe("/model/model-alpha");
  });

  it("applies the model-card-top class for rank 1", () => {
    const { container } = render(<ModelCard result={topResult} rank={1} />);
    expect(container.querySelector(".model-card-top")).toBeTruthy();
  });

  it("does not apply model-card-top for rank 2", () => {
    const { container } = render(<ModelCard result={secondResult} rank={2} />);
    expect(container.querySelector(".model-card-top")).toBeNull();
  });

  it("renders speed class based on tokens per second", () => {
    const { container: fast } = render(
      <ModelCard result={topResult} rank={1} />,
    );
    expect(fast.querySelector(".metric-good")).toBeTruthy();

    const { container: mid } = render(
      <ModelCard result={secondResult} rank={2} />,
    );
    expect(mid.querySelector(".metric-ok")).toBeTruthy();

    const { container: slow } = render(
      <ModelCard result={thirdResult} rank={3} />,
    );
    expect(slow.querySelector(".metric-slow")).toBeTruthy();
  });
});

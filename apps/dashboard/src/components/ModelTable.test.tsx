// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ModelTable from "./ModelTable";
import type { ModelSummary } from "../lib/loadResults";

function makeModel(id: string, overall: number): ModelSummary {
  return {
    model: `model-${id}`,
    metadata: { size: "7B", quantization: "Q4_K_M" },
    best_run_id: "run-1",
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
      tokens_per_sec: 50 + overall * 10,
      normalized_tps: 45 + overall * 10,
      ttft_ms: 400,
      total_latency_ms: 3000,
      memory_pressure_mb: 1400,
    },
    stats: { mean: overall, std: 0.05, runs: 5 },
    total_failures: 5,
    source: "local",
  };
}

const models = [
  makeModel("alpha", 0.92),  // S-tier
  makeModel("beta", 0.75),   // B-tier
  makeModel("gamma", 0.55),  // C-tier
];

describe("ModelTable", () => {
  it("renders all model names", () => {
    render(<ModelTable models={models} />);
    expect(screen.getByText("model-alpha")).toBeTruthy();
    expect(screen.getByText("model-beta")).toBeTruthy();
    expect(screen.getByText("model-gamma")).toBeTruthy();
  });

  it("renders column headers", () => {
    render(<ModelTable models={models} />);
    expect(screen.getByText("Model")).toBeTruthy();
    expect(screen.getByText("Coding")).toBeTruthy();
    expect(screen.getByText("Reasoning")).toBeTruthy();
    expect(screen.getByText("Instruct")).toBeTruthy();
    expect(screen.getByText("Tok/s")).toBeTruthy();
    expect(screen.getByText("Overall")).toBeTruthy();
  });

  it("sorts models by overall score descending", () => {
    render(<ModelTable models={models} />);
    const rows = screen.getAllByRole("row");
    expect(rows[1].textContent).toContain("model-alpha");
    expect(rows[2].textContent).toContain("model-beta");
    expect(rows[3].textContent).toContain("model-gamma");
  });

  it("renders tier badges for each model", () => {
    render(<ModelTable models={models} />);
    expect(screen.getByText("S-TIER")).toBeTruthy();
    expect(screen.getAllByText("B-TIER")).toHaveLength(1);
    expect(screen.getByText("C-TIER")).toBeTruthy();
  });

  it("highlights the top model with row-top class", () => {
    const { container } = render(<ModelTable models={models} />);
    const firstRow = container.querySelector("tbody tr");
    expect(firstRow?.classList.contains("row-top")).toBe(true);
  });

  it("renders scores as percentages", () => {
    render(<ModelTable models={models} />);
    expect(screen.getByText("92.0")).toBeTruthy();
  });

  it("renders tokens per second", () => {
    render(<ModelTable models={models} />);
    expect(screen.getByText("59.2")).toBeTruthy();
  });

  it("renders model metadata for all rows", () => {
    render(<ModelTable models={models} />);
    const metadataElements = screen.getAllByText("7B · Q4_K_M");
    expect(metadataElements).toHaveLength(3);
  });

  it("renders links to model detail pages", () => {
    render(<ModelTable models={models} />);
    const link = screen.getByText("model-alpha").closest("a");
    expect(link?.getAttribute("href")).toBe("/model/model-alpha");
  });

  it("handles empty models array", () => {
    const { container } = render(<ModelTable models={[]} />);
    const tbody = container.querySelector("tbody");
    expect(tbody?.children.length).toBe(0);
  });
});

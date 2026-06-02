// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LeaderboardTable from "./LeaderboardTable";
import type { ModelSummary } from "../lib/loadResults";

function makeModel(id: string, overall: number, coding: number, tps: number, source: "local" | "community" = "local"): ModelSummary {
  return {
    model: `model-${id}`,
    metadata: { size: "7B", quantization: "Q4_K_M" },
    best_run_id: "run-1",
    metrics: {
      coding_score: coding,
      reasoning_score: 0.7,
      instruction_score: 0.75,
      frontend_score: 0.65,
      math_score: 0.6,
      debugging_score: 0.55,
      overall_score: overall,
    },
    performance: {
      tokens_per_sec: tps,
      normalized_tps: tps * 0.95,
      ttft_ms: 400,
      total_latency_ms: 3000,
      memory_pressure_mb: 1400,
    },
    stats: { mean: overall, std: 0.05, runs: 5 },
    total_failures: 5,
    source,
  };
}

const models = [
  makeModel("alpha", 0.92, 0.88, 72),   // S-tier, gold
  makeModel("beta", 0.85, 0.82, 65),    // A-tier, silver
  makeModel("gamma", 0.78, 0.76, 58),   // B-tier, bronze
  makeModel("delta", 0.65, 0.7, 50),    // B-tier, no medal
  makeModel("epsilon", 0.55, 0.5, 42),  // C-tier, no medal
  makeModel("zeta", 0.3, 0.35, 35, "community"),   // F-tier, community
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("LeaderboardTable", () => {
  it("renders all model names", () => {
    render(<LeaderboardTable models={models} />);
    expect(screen.getByText("model-alpha")).toBeTruthy();
    expect(screen.getByText("model-beta")).toBeTruthy();
    expect(screen.getByText("model-gamma")).toBeTruthy();
    expect(screen.getByText("model-delta")).toBeTruthy();
    expect(screen.getByText("model-epsilon")).toBeTruthy();
    expect(screen.getByText("model-zeta")).toBeTruthy();
  });

  it("renders column headers", () => {
    render(<LeaderboardTable models={models} />);
    expect(screen.getByText("#")).toBeTruthy();
    expect(screen.getByText("Model")).toBeTruthy();
    expect(screen.getByText("Overall")).toBeTruthy();
    expect(screen.getByText("Speed")).toBeTruthy();
    expect(screen.getByText("Tier")).toBeTruthy();
    // "Coding" appears both as a header and a <select> option, so use getAllByText
    expect(screen.getAllByText("Coding").length).toBeGreaterThanOrEqual(1);
  });

  it("renders rank medals for top 3", () => {
    render(<LeaderboardTable models={models} />);
    // Gold, silver, bronze medals
    expect(screen.getByText("🥇")).toBeTruthy();
    expect(screen.getByText("🥈")).toBeTruthy();
    expect(screen.getByText("🥉")).toBeTruthy();
  });

  it("renders numeric ranks for positions 4+", () => {
    render(<LeaderboardTable models={models} />);
    expect(screen.getByText("04")).toBeTruthy();
    expect(screen.getByText("05")).toBeTruthy();
    expect(screen.getByText("06")).toBeTruthy();
  });

  it("sorts by overall score by default", () => {
    render(<LeaderboardTable models={models} />);
    const rows = screen.getAllByRole("row");
    // Header + 6 data rows = 7 rows
    expect(rows).toHaveLength(7);
    expect(rows[1].textContent).toContain("model-alpha");
    expect(rows[6].textContent).toContain("model-zeta");
  });

  it("computes correct percentage for overall score", () => {
    render(<LeaderboardTable models={models} />);
    // model-alpha overall: 0.92 * 100 = 92.0%
    expect(screen.getByText("92.0%")).toBeTruthy();
    // model-zeta overall: 0.3 * 100 = 30.0%
    expect(screen.getByText("30.0%")).toBeTruthy();
  });

  it("computes correct coding score percentage", () => {
    render(<LeaderboardTable models={models} />);
    expect(screen.getByText("88.0")).toBeTruthy();
    expect(screen.getByText("35.0")).toBeTruthy();
  });

  it("renders tier badges", () => {
    render(<LeaderboardTable models={models} />);
    expect(screen.getByText("S-TIER")).toBeTruthy();
    expect(screen.getByText("A-TIER")).toBeTruthy();
    // B-TIER appears twice (model-gamma and model-delta)
    expect(screen.getAllByText("B-TIER")).toHaveLength(2);
    expect(screen.getByText("C-TIER")).toBeTruthy();
    expect(screen.getByText("F-TIER")).toBeTruthy();
  });

  it("renders tokens per second", () => {
    render(<LeaderboardTable models={models} />);
    expect(screen.getByText("72")).toBeTruthy();
    expect(screen.getByText("35")).toBeTruthy();
  });

  it('shows community badge for community-sourced models', () => {
    render(<LeaderboardTable models={models} />);
    const badges = document.querySelectorAll(".source-badge");
    expect(badges.length).toBe(1); // only model-zeta is community
    expect(badges[0].textContent).toContain("community");
  });

  it("renders sort controls with default 'overall'", () => {
    render(<LeaderboardTable models={models} />);
    const select = screen.getByRole("combobox");
    expect((select as HTMLSelectElement).value).toBe("overall");
    expect(screen.getByText("SORT BY:")).toBeTruthy();
  });

  it("re-sorts by coding score when sorted selected changes", async () => {
    const user = userEvent.setup();
    render(<LeaderboardTable models={models} />);

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "coding");

    // After sorting by coding, model-alpha still first (coding 0.88)
    const rows = screen.getAllByRole("row");
    expect(rows[1].textContent).toContain("model-alpha");
    // model-zeta last (coding 0.35)
    expect(rows[6].textContent).toContain("model-zeta");
  });

  it("re-sorts by throughput when sort option selected", async () => {
    const user = userEvent.setup();
    render(<LeaderboardTable models={models} />);

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "throughput");

    // After sorting by throughput, model-alpha still first (tps 72)
    const rows = screen.getAllByRole("row");
    expect(rows[1].textContent).toContain("model-alpha");
  });

  it("renders progress bars with correct width", () => {
    const { container } = render(<LeaderboardTable models={models} />);
    const fills = container.querySelectorAll(".lb-bar-fill");
    expect(fills.length).toBe(6);
    // model-alpha: 92% → width: 92%
    expect((fills[0] as HTMLElement).style.width).toBe("92%");
    // model-zeta: 30% → width: 30%
    expect((fills[5] as HTMLElement).style.width).toBe("30%");
  });

  it("renders links to model detail pages", () => {
    render(<LeaderboardTable models={models} />);
    const link = screen.getByText("model-alpha").closest("a");
    expect(link?.getAttribute("href")).toBe("/model/model-alpha");
  });

  it("handles empty models array", () => {
    const { container } = render(<LeaderboardTable models={[]} />);
    const tbody = container.querySelector("tbody");
    expect(tbody?.children.length).toBe(0);
  });

  it("shows count in the footnote", () => {
    render(<LeaderboardTable models={models} />);
    expect(screen.getByText(/6 models/)).toBeTruthy();
  });
});

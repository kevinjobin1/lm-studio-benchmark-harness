// @vitest-environment jsdom
/**
 * Integration tests for the dashboard data pipeline.
 *
 * Tests flow real results.json fixture data through the full pipeline:
 *   loadResults (mocked fetch) → buildLeaderboard → component rendering
 *
 * Also tests data-processing utilities with real data shapes.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  buildLeaderboard,
  groupByModel,
  aggregateFailures,
  loadResults,
  loadAllResults,
} from "./lib/loadResults";
import {
  loadTraceManifest,
  loadTrace,
  loadTraceList,
  mapTraceToRun,
} from "./lib/loadTraces";
import {
  loadReplayManifest,
  loadReplay,
  loadReplayList,
} from "./lib/loadReplays";
import type {
  TraceManifest,
  TraceData,
  TraceIndexEntry,
} from "./lib/loadTraces";
import type {
  ReplayManifest,
  ReplayData,
  ReplayIndexEntry,
} from "./lib/loadReplays";
import TraceTimeline from "./components/TraceTimeline";
import ReplayViewer from "./components/ReplayViewer";
import ReplayToast from "./components/ReplayToast";
import ReplaySidebarBadge from "./components/ReplaySidebarBadge";
import RunBenchmarkButton from "./components/RunBenchmarkButton";
import ModelTable from "./components/ModelTable";
import LeaderboardTable from "./components/LeaderboardTable";
import ModelCard from "./components/ModelCard";
import type {
  AggregatedResults,
  BenchmarkResult,
  ModelSummary,
} from "./lib/loadResults";

// ── Fixture Data ──────────────────────────────────────────────────
// This is the real results.json content, used to test the full pipeline.

const fixtureData: AggregatedResults = {
  version: "1.0.0",
  generated_at: "2026-06-01T13:30:29.604552",
  total_models: 2,
  total_runs: 2,
  runs: [
    {
      run_id: "real_google_gemma-4-e4b",
      model: "google/gemma-4-e4b",
      model_metadata: { size: "4B", quantization: "Q4_K_M" },
      hardware: {
        platform: "macOS 15.6.1",
        processor: "Apple M3 Pro",
        memory_gb: 18,
        architecture: "arm64",
      },
      timestamp: "2026-06-01T13:30:29.604526",
      git_sha: "main",
      git_branch: "main",
      metrics: {
        coding_score: 0.375,
        reasoning_score: 0.6667,
        instruction_score: 0.3333,
        frontend_score: 0.726,
        math_score: 0.1666,
        debugging_score: 1.0,
        overall_score: 0.4893,
      },
      performance: {
        tokens_per_sec: 3.08,
        normalized_tps: 2.93,
        ttft_ms: 19040,
        total_latency_ms: 21540,
        memory_pressure_mb: 25.6,
      },
      stats: {
        mean: 0.4893,
        std: 0.05,
        min: 0.0,
        max: 1.0,
        median: 0.6667,
        runs: 5,
        confidence_95: [0.4393, 0.5393],
        coefficient_of_variation: 0.12,
      },
      failures: {
        hallucinated_api: 0,
        wrong_async_usage: 1,
        incorrect_json_schema: 0,
        syntax_error: 0,
        logic_error: 2,
        type_error: 1,
        missing_import: 0,
        stale_closure: 0,
        race_condition: 0,
        incorrect_di: 0,
        oververbose: 1,
        missed_constraint: 1,
        other: 1,
      },
      category_scores: {
        mmlu_pro: { accuracy: 0.6667 },
        gsm8k: { accuracy: 0.3333 },
        aime: { accuracy: 0.0 },
        bfcl: { tool_use_accuracy: 1.0 },
        humaneval: { "pass@1": 0.0 },
        swe_bench_lite: { task_quality: 0.75 },
        if_eval: { instruction_following: 0.3333 },
        needle_in_haystack: { retrieval_accuracy: 1.0 },
        creativity: { creativity_score: 0.726 },
      },
      config_snapshot: { temperature: 0.0, max_tokens: 1000 },
      prompt_version: "v1",
      packs_used: ["nestjs-pack", "react-pack", "debugging-pack"],
      seed: 42,
    },
    {
      run_id: "real_lfm2.5-8b-a1b",
      model: "lfm2.5-8b-a1b",
      model_metadata: { size: "8B", quantization: "Q4_K_M", type: "reasoning" },
      hardware: {
        platform: "macOS 15.6.1",
        processor: "Apple M3 Pro",
        memory_gb: 18,
        architecture: "arm64",
      },
      timestamp: "2026-06-01T13:30:29.604546",
      git_sha: "main",
      git_branch: "main",
      metrics: {
        coding_score: 0.3125,
        reasoning_score: 1.0,
        instruction_score: 0.6667,
        frontend_score: 0.7172,
        math_score: 1.0,
        debugging_score: 0.25,
        overall_score: 0.6301,
      },
      performance: {
        tokens_per_sec: 15.15,
        normalized_tps: 14.39,
        ttft_ms: 7630,
        total_latency_ms: 10130,
        memory_pressure_mb: 23.0,
      },
      stats: {
        mean: 0.6301,
        std: 0.05,
        min: 0.0,
        max: 1.0,
        median: 0.6667,
        runs: 5,
        confidence_95: [0.5801, 0.6801],
        coefficient_of_variation: 0.12,
      },
      failures: {
        hallucinated_api: 1,
        wrong_async_usage: 1,
        incorrect_json_schema: 0,
        syntax_error: 0,
        logic_error: 2,
        type_error: 1,
        missing_import: 0,
        stale_closure: 0,
        race_condition: 0,
        incorrect_di: 0,
        oververbose: 1,
        missed_constraint: 1,
        other: 1,
      },
      category_scores: {
        mmlu_pro: { accuracy: 1.0 },
        gsm8k: { accuracy: 1.0 },
        aime: { accuracy: 1.0 },
        bfcl: { tool_use_accuracy: 0.6667 },
        humaneval: { "pass@1": 0.0 },
        swe_bench_lite: { task_quality: 0.625 },
        if_eval: { instruction_following: 0.6667 },
        needle_in_haystack: { retrieval_accuracy: 0.25 },
        creativity: { creativity_score: 0.7172 },
      },
      config_snapshot: { temperature: 0.0, max_tokens: 1000 },
      prompt_version: "v1",
      packs_used: ["nestjs-pack", "react-pack", "debugging-pack"],
      seed: 42,
    },
  ],
};

const results = fixtureData.runs as BenchmarkResult[];

afterEach(() => {
  vi.restoreAllMocks();
});

// ═══════════════════════════════════════════════════════════════════
// DATA PIPELINE TESTS
// ═══════════════════════════════════════════════════════════════════

describe("Data pipeline — buildLeaderboard", () => {
  let leaderboard: ReturnType<typeof buildLeaderboard>;

  beforeEach(() => {
    leaderboard = buildLeaderboard(results);
  });

  it("produces correct number of models", () => {
    expect(leaderboard.leaderboard.length).toBe(2);
    expect(leaderboard.localCount).toBe(2);
  });

  it("sorts models by overall score descending", () => {
    const [first, second] = leaderboard.leaderboard;
    // lfm2.5-8b-a1b: 0.6301 > google/gemma-4-e4b: 0.4893
    expect(first.model).toBe("lfm2.5-8b-a1b");
    expect(second.model).toBe("google/gemma-4-e4b");
  });

  it("preserves model metadata", () => {
    const gemma = leaderboard.leaderboard.find(
      (m) => m.model === "google/gemma-4-e4b",
    )!;
    expect(gemma.metadata.size).toBe("4B");
    expect(gemma.metadata.quantization).toBe("Q4_K_M");
  });

  it("computes total_failures correctly", () => {
    const lfm = leaderboard.leaderboard.find(
      (m) => m.model === "lfm2.5-8b-a1b",
    )!;
    // hallucinated_api:1 + wrong_async_usage:1 + logic_error:2 + type_error:1
    // + oververbose:1 + missed_constraint:1 + other:1 = 8
    expect(lfm.total_failures).toBe(8);
  });

  it("preserves performance metrics in leaderboard", () => {
    const lfm = leaderboard.leaderboard[0];
    expect(lfm.performance.tokens_per_sec).toBe(15.15);
    expect(lfm.performance.ttft_ms).toBe(7630);
  });

  it("preserves all metrics scores", () => {
    const gemma = leaderboard.leaderboard[1];
    expect(gemma.metrics.coding_score).toBe(0.375);
    expect(gemma.metrics.reasoning_score).toBe(0.6667);
    expect(gemma.metrics.instruction_score).toBe(0.3333);
    expect(gemma.metrics.overall_score).toBe(0.4893);
  });

  it("marks all models as source 'local'", () => {
    for (const m of leaderboard.leaderboard) {
      expect(m.source).toBe("local");
    }
  });

  it("preserves the best_run_id", () => {
    const gemma = leaderboard.leaderboard[1];
    expect(gemma.best_run_id).toBe("real_google_gemma-4-e4b");
  });

  it("generates a generated_at timestamp", () => {
    expect(leaderboard.generated_at).toBeTruthy();
    expect(typeof leaderboard.generated_at).toBe("string");
  });
});

describe("Data pipeline — groupByModel", () => {
  it("groups results by model", () => {
    const grouped = groupByModel(results);
    expect(grouped.size).toBe(2);
    expect(grouped.has("google/gemma-4-e4b")).toBe(true);
    expect(grouped.has("lfm2.5-8b-a1b")).toBe(true);
  });

  it("each group contains the correct number of results", () => {
    const grouped = groupByModel(results);
    expect(grouped.get("google/gemma-4-e4b")?.length).toBe(1);
    expect(grouped.get("lfm2.5-8b-a1b")?.length).toBe(1);
  });

  it("returns empty map for empty array", () => {
    const grouped = groupByModel([]);
    expect(grouped.size).toBe(0);
  });

  it("groups multiple runs for the same model", () => {
    const multiRunResults = [
      ...results,
      {
        ...results[0],
        run_id: "real_google_gemma-4-e4b-run2",
        stats: { ...results[0].stats, runs: 3 },
      },
    ];
    const grouped = groupByModel(multiRunResults);
    expect(grouped.get("google/gemma-4-e4b")?.length).toBe(2);
  });
});

describe("Data pipeline — aggregateFailures", () => {
  it("aggregates failures across all results", () => {
    const aggregated = aggregateFailures(results);
    // Should have multiple failure types with non-zero counts
    expect(aggregated.labels.length).toBeGreaterThan(0);
    expect(aggregated.counts.length).toBe(aggregated.labels.length);
  });

  it("sorts failures by count descending", () => {
    const aggregated = aggregateFailures(results);
    for (let i = 1; i < aggregated.counts.length; i++) {
      expect(aggregated.counts[i - 1]).toBeGreaterThanOrEqual(
        aggregated.counts[i],
      );
    }
  });

  it("produces human-readable labels", () => {
    const aggregated = aggregateFailures(results);
    // Labels should be human-readable, not raw keys
    for (const label of aggregated.labels) {
      expect(label).not.toMatch(/_/);
    }
  });

  it("only includes failure types with non-zero totals", () => {
    const aggregated = aggregateFailures(results);
    // Both runs have 0 hallucinated_api, but they have other failures
    // so there should be at least some labels
    expect(aggregated.labels.length).toBeGreaterThan(0);
    expect(aggregated.counts.every((c) => c > 0)).toBe(true);
  });

  it("returns empty arrays when no failures", () => {
    const noFailures = results.map((r) => ({
      ...r,
      failures: Object.fromEntries(
        Object.entries(r.failures).map(([k]) => [k, 0]),
      ) as BenchmarkResult["failures"],
    }));
    const aggregated = aggregateFailures(noFailures);
    expect(aggregated.labels.length).toBe(0);
    expect(aggregated.counts.length).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// COMPONENT RENDERING TESTS (with real data)
// ═══════════════════════════════════════════════════════════════════

describe("ModelTable — rendered with real leaderboard data", () => {
  let leaderboard: ReturnType<typeof buildLeaderboard>;

  beforeEach(() => {
    leaderboard = buildLeaderboard(results);
  });

  it("renders both model names from real data", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("google/gemma-4-e4b")).toBeTruthy();
    expect(screen.getByText("lfm2.5-8b-a1b")).toBeTruthy();
  });

  it("renders column headers", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("Model")).toBeTruthy();
    expect(screen.getByText("Coding")).toBeTruthy();
    expect(screen.getByText("Reasoning")).toBeTruthy();
    expect(screen.getByText("Instruct")).toBeTruthy();
    expect(screen.getByText("Tok/s")).toBeTruthy();
    expect(screen.getByText("Overall")).toBeTruthy();
  });

  it("sorts by overall score (lfm2.5 first, gemma second)", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    const rows = screen.getAllByRole("row");
    // Row 0 is header, row 1 is first model (lfm2.5), row 2 is second (gemma)
    expect(rows[1].textContent).toContain("lfm2.5-8b-a1b");
    expect(rows[2].textContent).toContain("google/gemma-4-e4b");
  });

  it("renders correct overall scores as percentages", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    // lfm2.5: 0.6301 → 63.0%, gemma: 0.4893 → 48.9%
    expect(screen.getByText("63.0")).toBeTruthy();
    expect(screen.getByText("48.9")).toBeTruthy();
  });

  it("renders tokens per second values", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("15.2")).toBeTruthy(); // lfm2.5 tps (15.15 → "15.2" in V8)
    expect(screen.getByText("3.1")).toBeTruthy(); // gemma tps (3.08 → "3.1")
  });

  it("renders correct tier badges", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    // lfm2.5: 0.6301 >= 0.5 → C-TIER (0.6301 >= 0.5 but < 0.65)
    // gemma: 0.4893 < 0.5 → F-TIER
    expect(screen.getByText("C-TIER")).toBeTruthy();
    expect(screen.getByText("F-TIER")).toBeTruthy();
  });

  it("renders model metadata chips (size + quantization)", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("8B · Q4_K_M")).toBeTruthy();
    expect(screen.getByText("4B · Q4_K_M")).toBeTruthy();
  });

  it("renders coding and reasoning scores", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    // lfm2.5: coding=0.3125 → 31.3, gemma: coding=0.375 → 37.5
    expect(screen.getByText("31.3")).toBeTruthy();
    expect(screen.getByText("37.5")).toBeTruthy();
  });

  it("highlights the top model with row-top class", () => {
    const { container } = render(
      <ModelTable models={leaderboard.leaderboard} />,
    );
    const firstRow = container.querySelector("tbody tr");
    expect(firstRow?.classList.contains("row-top")).toBe(true);
  });

  it("renders links to model detail pages", () => {
    render(<ModelTable models={leaderboard.leaderboard} />);
    const lfmLink = screen.getByText("lfm2.5-8b-a1b").closest("a");
    expect(lfmLink?.getAttribute("href")).toBe("/model/lfm2.5-8b-a1b");

    const gemmaLink = screen.getByText("google/gemma-4-e4b").closest("a");
    expect(gemmaLink?.getAttribute("href")).toBe("/model/google%2Fgemma-4-e4b");
  });
});

describe("LeaderboardTable — rendered with real leaderboard data", () => {
  let leaderboard: ReturnType<typeof buildLeaderboard>;

  beforeEach(() => {
    leaderboard = buildLeaderboard(results);
  });

  it("renders both model names", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("google/gemma-4-e4b")).toBeTruthy();
    expect(screen.getByText("lfm2.5-8b-a1b")).toBeTruthy();
  });

  it("renders column headers", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("#")).toBeTruthy();
    expect(screen.getByText("Model")).toBeTruthy();
    expect(screen.getByText("Overall")).toBeTruthy();
    // "Coding" appears both as a <th> header AND as an <option> in the sort select
    expect(screen.getAllByText("Coding").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Speed")).toBeTruthy();
    expect(screen.getByText("Tier")).toBeTruthy();
  });

  it("shows gold medal for #1 (lfm2.5)", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("🥇")).toBeTruthy();
  });

  it("shows silver medal for #2 (gemma)", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("🥈")).toBeTruthy();
  });

  it("renders overall score percentages", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    // lfm2.5: 63.01% → 63.0%, gemma: 48.93% → 48.9%
    expect(screen.getByText("63.0%")).toBeTruthy();
    expect(screen.getByText("48.9%")).toBeTruthy();
  });

  it("renders coding scores", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    // lfm2.5: 0.3125 → 31.3, gemma: 0.375 → 37.5
    expect(screen.getByText("31.3")).toBeTruthy();
    expect(screen.getByText("37.5")).toBeTruthy();
  });

  it("renders tokens per second with tok/s unit", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    // lfm2.5: 15.15 → "15" tok/s, gemma: 3.08 → "3" tok/s
    const speedValues = screen
      .getAllByText(/^\d+$/)
      .filter((el) => el.textContent === "15" || el.textContent === "3");
    expect(speedValues.length).toBeGreaterThanOrEqual(2);
  });

  it("renders tier badges", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("C-TIER")).toBeTruthy();
    expect(screen.getByText("F-TIER")).toBeTruthy();
  });

  it("renders the sort select with sort controls", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    expect(screen.getByText("SORT BY:")).toBeTruthy();
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("overall");
  });

  it("renders the footnote with model count", () => {
    render(<LeaderboardTable models={leaderboard.leaderboard} />);
    expect(screen.getByText(/2 models/)).toBeTruthy();
    expect(screen.getByText(/Apple Silicon/)).toBeTruthy();
  });

  it("renders progress bars with correct widths", () => {
    const { container } = render(
      <LeaderboardTable models={leaderboard.leaderboard} />,
    );
    const bars = container.querySelectorAll(".lb-bar-fill");
    expect(bars.length).toBe(2);
    // lfm2.5: 0.6301 * 100 = 63.01 (no toFixed on inline style)
    expect((bars[0] as HTMLElement).style.width).toBe("63.01%");
  });
});

describe("ModelCard — rendered with real BenchmarkResult data", () => {
  it("renders the top-ranked model with gold medal", () => {
    render(<ModelCard result={results[1]} rank={1} />);
    // lfm2.5 is results[1], rank 1
    expect(screen.getByText("lfm2.5-8b-a1b")).toBeTruthy();
    expect(screen.getByText("🥇")).toBeTruthy();
  });

  it("renders overall score for lfm2.5", () => {
    render(<ModelCard result={results[1]} rank={1} />);
    expect(screen.getByText("63.0%")).toBeTruthy();
  });

  it("renders correct tier label for lfm2.5 (C-TIER)", () => {
    render(<ModelCard result={results[1]} rank={1} />);
    expect(screen.getByText("C-TIER")).toBeTruthy();
  });

  it("renders correct tier for gemma (F-TIER)", () => {
    render(<ModelCard result={results[0]} rank={2} />);
    expect(screen.getByText("F-TIER")).toBeTruthy();
  });

  it("renders model metadata chips (size and quantization)", () => {
    render(<ModelCard result={results[0]} rank={2} />);
    expect(screen.getByText("4B")).toBeTruthy();
    expect(screen.getByText("Q4_K_M")).toBeTruthy();
  });

  it("renders metric rows with percentage values", () => {
    render(<ModelCard result={results[0]} rank={2} />);
    // gemma: coding=0.375 → 38%, reasoning=0.6667 → 67%, instructions=0.3333 → 33%
    expect(screen.getByText("38%")).toBeTruthy();
    expect(screen.getByText("67%")).toBeTruthy();
    expect(screen.getByText("33%")).toBeTruthy();
  });

  it("renders performance badges (tps, ttft, runs)", () => {
    render(<ModelCard result={results[0]} rank={2} />);
    // gemma: tps=3.08 → "3", ttft=19040 → "19040", runs=5 → "5"
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("19040")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
  });

  it("renders confidence interval text", () => {
    render(<ModelCard result={results[0]} rank={2} />);
    // gemma: CI [0.4393, 0.5393] → "43.9%, 53.9%"
    expect(screen.getByText(/43\.9%.*53\.9%/)).toBeTruthy();
  });

  it("renders a link to the model detail page", () => {
    render(<ModelCard result={results[0]} rank={1} />);
    const link = screen.getByText("48.9%").closest("a");
    expect(link?.getAttribute("href")).toBe("/model/google%2Fgemma-4-e4b");
  });

  it("applies model-card-top class for rank 1", () => {
    const { container } = render(<ModelCard result={results[1]} rank={1} />);
    expect(container.querySelector(".model-card-top")).toBeTruthy();
  });

  it("speed badge uses metric-slow class for low tps", () => {
    const { container } = render(<ModelCard result={results[0]} rank={2} />);
    // gemma: tps=3.08 — well below 45, so metric-slow
    expect(container.querySelector(".metric-slow")).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════
// END-TO-END PIPELINE TEST
// ═══════════════════════════════════════════════════════════════════

describe("End-to-end pipeline — mocked fetch → loadResults → buildLeaderboard → render", () => {
  beforeEach(() => {
    // Mock fetch to return the fixture data (as loadResults would receive it)
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(fixtureData),
    });
  });

  it("loadResults fetches from /results.json and returns parsed data", async () => {
    const data = await loadResults();
    expect(data.length).toBe(2);
    expect(data[0].model).toBe("google/gemma-4-e4b");
    expect(data[1].model).toBe("lfm2.5-8b-a1b");
    expect(global.fetch).toHaveBeenCalledWith("/results.json");
  });

  it("buildLeaderboard processes loadResults output correctly", async () => {
    const data = await loadResults();
    const leaderboard = buildLeaderboard(data);
    expect(leaderboard.leaderboard.length).toBe(2);
    // lfm2.5 has higher overall score (0.6301 > 0.4893)
    expect(leaderboard.leaderboard[0].model).toBe("lfm2.5-8b-a1b");
    expect(leaderboard.leaderboard[1].model).toBe("google/gemma-4-e4b");
  });

  it("ModelTable renders correctly from the full pipeline", async () => {
    const data = await loadResults();
    const { leaderboard: models } = buildLeaderboard(data);

    render(<ModelTable models={models} />);

    expect(screen.getByText("lfm2.5-8b-a1b")).toBeTruthy();
    expect(screen.getByText("google/gemma-4-e4b")).toBeTruthy();
    expect(screen.getByText("63.0")).toBeTruthy();
    expect(screen.getByText("48.9")).toBeTruthy();
  });

  it("LeaderboardTable renders correctly from the full pipeline", async () => {
    const data = await loadResults();
    const { leaderboard: models } = buildLeaderboard(data);

    render(<LeaderboardTable models={models} />);

    expect(screen.getByText("🥇")).toBeTruthy();
    expect(screen.getByText("🥈")).toBeTruthy();
    expect(screen.getByText("C-TIER")).toBeTruthy();
    expect(screen.getByText("F-TIER")).toBeTruthy();
    expect(screen.getByText(/2 models/)).toBeTruthy();
  });

  it("loadAllResults merges local and community results", async () => {
    // Mock leaderboard.json as well
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/results.json") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(fixtureData),
        });
      }
      if (url === "/leaderboard.json") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              models: [
                {
                  model: "community-model-v1",
                  metadata: { size: "7B" },
                  best_run_id: "community-run-1",
                  metrics: {
                    coding_score: 0.7,
                    reasoning_score: 0.65,
                    instruction_score: 0.75,
                    frontend_score: 0.6,
                    math_score: 0.6,
                    debugging_score: 0.55,
                    overall_score: 0.68,
                  },
                  performance: {
                    tokens_per_sec: 50,
                    normalized_tps: 47.5,
                    ttft_ms: 500,
                    total_latency_ms: 3000,
                    memory_pressure_mb: 1000,
                  },
                  stats: { mean: 0.68, std: 0.05, runs: 3 },
                  total_failures: 2,
                },
              ],
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    const allData = await loadAllResults();
    // 2 local + 1 community (no duplicates)
    expect(allData.leaderboard.length).toBe(3);
    expect(allData.localCount).toBe(2);
    expect(allData.communityCount).toBe(1);

    // Community model should have source: "community"
    const communityModel = allData.leaderboard.find(
      (m) => m.model === "community-model-v1",
    );
    expect(communityModel?.source).toBe("community");
  });

  it("handles network error gracefully in the pipeline", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network failure"));

    // loadResults falls back to generateDemoData on error
    const data = await loadResults();
    // Demo data has 3 models
    expect(data.length).toBe(3);

    const leaderboard = buildLeaderboard(data);
    expect(leaderboard.leaderboard.length).toBe(3);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TRACES FIXTURES
// ═══════════════════════════════════════════════════════════════════

const traceManifestFixture: TraceManifest = {
  version: "1.0.0",
  generated_at: "2026-06-02T14:30:00Z",
  total_traces: 2,
  traces: [
    {
      trace_id: "trace-nestjs-jwt",
      run_id: "run-8821",
      model: "google/gemma-4-e4b",
      provider: "lm-studio",
      prompt: "auth/JWT Guard Implementation",
      timestamp: "2026-06-02T14:14:00Z",
      totalTimeMs: 4820,
      status: "completed",
      stepCount: 5,
      tokenCount: 156,
      ttft_ms: 220,
    },
    {
      trace_id: "trace-debug-race",
      run_id: "run-7712",
      model: "lfm2.5-8b-a1b",
      provider: "lm-studio",
      prompt: "debug_race_condition/Async Queue",
      timestamp: "2026-06-02T11:02:00Z",
      totalTimeMs: 6230,
      status: "failed",
      stepCount: 7,
      tokenCount: 89,
      ttft_ms: 410,
    },
  ],
};

const traceDataFixtures: Record<string, TraceData> = {
  "trace-nestjs-jwt": {
    trace_id: "trace-nestjs-jwt",
    run_id: "run-8821",
    model: "google/gemma-4-e4b",
    provider: "lm-studio",
    prompt: "auth/JWT Guard Implementation",
    system_prompt: "You are a NestJS backend engineer.",
    pack: "nestjs-pack",
    timestamp: "2026-06-02T14:14:00Z",
    totalTimeMs: 4820,
    status: "completed",
    steps: [
      {
        id: "s0",
        type: "system",
        label: "System Instruction",
        detail: "You are a NestJS backend engineer. Implement with proper error handling.",
        timing_ms: 0,
        status: "success",
      },
      {
        id: "s1",
        type: "tool_call",
        label: "Calling: prisma.user.findUnique",
        tool: "prisma_user_service",
        input: '{ id: "user_123" }',
        timing_ms: 42,
        status: "success",
      },
      {
        id: "s2",
        type: "reasoning",
        label: "Analyzing schema relations",
        detail: "User → Posts (1:M), User → Profile (1:1). Need to include both relations.",
        timing_ms: 28,
        status: "success",
      },
      {
        id: "s3",
        type: "tool_call",
        label: "Calling: prisma.user.findUnique (with includes)",
        tool: "prisma_user_service",
        input: '{ id: "user_123", include: { posts: true, profile: true } }',
        timing_ms: 38,
        status: "success",
      },
      {
        id: "s4",
        type: "response",
        label: "Generated Implementation",
        detail: "Exported UserService.getUserWithRelations() with Prisma includes and error handling.",
        timing_ms: 156,
        status: "success",
      },
    ],
    metrics: {
      ttft_ms: 220,
      tokens_per_second: 42.5,
      total_tokens: 156,
      prompt_tokens: 48,
      completion_tokens: 108,
      total_latency_ms: 4820,
      memory_pressure_mb: 3200,
      token_timings_ms: [12, 14, 11, 15, 13],
    },
    artifacts: {
      response: "Exported UserService.getUserWithRelations()",
      logs: ["[2026-06-02T14:14:00Z] Trace trace-nestjs-jwt captured"],
      errors: [],
    },
    hardware: {
      platform: "macOS 15.6.1",
      processor: "Apple M3 Pro",
      memory_gb: 18,
      architecture: "arm64",
    },
  },
  "trace-debug-race": {
    trace_id: "trace-debug-race",
    run_id: "run-7712",
    model: "lfm2.5-8b-a1b",
    provider: "lm-studio",
    prompt: "debug_race_condition/Async Queue",
    system_prompt: null,
    pack: "debugging-pack",
    timestamp: "2026-06-02T11:02:00Z",
    totalTimeMs: 6230,
    status: "failed",
    steps: [
      {
        id: "s0",
        type: "system",
        label: "System Instruction",
        detail: "Find and fix the race condition.",
        timing_ms: 0,
        status: "success",
      },
      {
        id: "s1",
        type: "reasoning",
        label: "Identifying the race condition",
        detail: "Promise.all on line 42 fires concurrent writes to same cache key.",
        timing_ms: 45,
        status: "success",
      },
      {
        id: "s2",
        type: "tool_call",
        label: "Calling: grep for cache.set",
        tool: "file_search",
        input: "cache.set",
        timing_ms: 18,
        status: "success",
      },
      {
        id: "s3",
        type: "error",
        label: "Error: Race condition unresolved",
        detail: "Concurrent writes detected — mutex required.",
        timing_ms: 120,
        status: "failure",
      },
      {
        id: "s4",
        type: "response",
        label: "Failed to resolve",
        detail: "Race condition could not be fully resolved within timeout.",
        timing_ms: 300,
        status: "failure",
      },
    ],
    metrics: {
      ttft_ms: 410,
      tokens_per_second: 28.1,
      total_tokens: 89,
      prompt_tokens: 32,
      completion_tokens: 57,
      total_latency_ms: 6230,
      memory_pressure_mb: 2800,
      token_timings_ms: [20, 18, 22, 19],
    },
    artifacts: {
      response: "Race condition partially addressed. Consider using async-mutex.",
      logs: ["[2026-06-02T11:02:00Z] Trace trace-debug-race captured"],
      errors: ["Race condition: concurrent cache.set detected at line 42"],
    },
    hardware: {
      platform: "macOS 15.6.1",
      processor: "Apple M3 Pro",
      memory_gb: 18,
      architecture: "arm64",
    },
  },
};

// ═══════════════════════════════════════════════════════════════════
// TRACES END-TO-END PIPELINE TESTS
// ═══════════════════════════════════════════════════════════════════

describe("Traces E2E — manifest → API → component render", () => {
  beforeEach(() => {
    // jsdom doesn't implement scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();

    // Mock fetch for browser-mode trace loading.
    // loadTraceManifest → GET /traces/index.json
    // loadTrace → GET /api/traces/{id}
    // loadTraceList → GET /api/traces?model=...
    global.fetch = vi.fn().mockImplementation((url: string) => {
      const urlStr = String(url);

      // Manifest
      if (urlStr === "/traces/index.json") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(traceManifestFixture),
        });
      }

      // Single trace: /api/traces/{id}
      const singleMatch = urlStr.match(/^\/api\/traces\/(.+)$/);
      if (singleMatch) {
        const id = decodeURIComponent(singleMatch[1]);
        const data = traceDataFixtures[id];
        if (data) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(data),
          });
        }
        return Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ error: "not found" }),
        });
      }

      // Trace list: /api/traces
      if (urlStr.startsWith("/api/traces")) {
        const params = new URL(urlStr, "http://localhost").searchParams;
        let filtered = [...traceManifestFixture.traces];
        const model = params.get("model");
        const status = params.get("status");
        const limit = parseInt(params.get("limit") || "", 10) || undefined;
        const offset = parseInt(params.get("offset") || "", 10) || 0;
        if (model) {
          filtered = filtered.filter((t) =>
            t.model.toLowerCase().includes(model.toLowerCase()),
          );
        }
        if (status) {
          filtered = filtered.filter((t) => t.status === status);
        }
        // Sort by timestamp descending (matches filterManifest behavior)
        filtered.sort(
          (a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
        );
        const sliced = limit !== undefined
          ? filtered.slice(offset, offset + limit)
          : filtered.slice(offset);
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(sliced),
        });
      }

      return Promise.reject(new Error(`Unmocked URL: ${urlStr}`));
    });
  });

  // ── Manifest loading ──────────────────────────────────────

  it("loadTraceManifest returns the manifest with correct structure", async () => {
    const manifest = await loadTraceManifest();
    expect(manifest.version).toBe("1.0.0");
    expect(manifest.total_traces).toBe(2);
    expect(manifest.traces.length).toBe(2);
    expect(global.fetch).toHaveBeenCalledWith("/traces/index.json");
  });

  it("loadTraceManifest entries have correct fields", async () => {
    const manifest = await loadTraceManifest();
    const entry = manifest.traces[0];
    expect(entry.trace_id).toBe("trace-nestjs-jwt");
    expect(entry.model).toBe("google/gemma-4-e4b");
    expect(entry.provider).toBe("lm-studio");
    expect(entry.status).toBe("completed");
    expect(entry.stepCount).toBe(5);
    expect(entry.tokenCount).toBe(156);
    expect(entry.ttft_ms).toBe(220);
  });

  // ── Single trace loading ──────────────────────────────────

  it("loadTrace returns a single trace by ID", async () => {
    const trace = await loadTrace("trace-nestjs-jwt");
    expect(trace).not.toBeNull();
    expect(trace!.trace_id).toBe("trace-nestjs-jwt");
    expect(trace!.model).toBe("google/gemma-4-e4b");
    expect(trace!.status).toBe("completed");
    expect(trace!.steps.length).toBe(5);
  });

  it("loadTrace returns null for non-existent trace", async () => {
    const trace = await loadTrace("nonexistent-trace");
    expect(trace).toBeNull();
  });

  it("loadTrace returns full step data with types and timing", async () => {
    const trace = await loadTrace("trace-nestjs-jwt");
    expect(trace).not.toBeNull();
    const steps = trace!.steps;

    expect(steps[0].type).toBe("system");
    expect(steps[0].label).toBe("System Instruction");
    expect(steps[0].status).toBe("success");

    expect(steps[1].type).toBe("tool_call");
    expect(steps[1].tool).toBe("prisma_user_service");
    expect(steps[1].input).toContain("user_123");
    expect(steps[1].timing_ms).toBe(42);

    expect(steps[2].type).toBe("reasoning");
    expect(steps[4].type).toBe("response");
  });

  it("loadTrace returns metrics and artifacts", async () => {
    const trace = await loadTrace("trace-debug-race");
    expect(trace).not.toBeNull();

    expect(trace!.metrics.ttft_ms).toBe(410);
    expect(trace!.metrics.tokens_per_second).toBe(28.1);
    expect(trace!.metrics.total_tokens).toBe(89);
    expect(trace!.metrics.memory_pressure_mb).toBe(2800);

    expect(trace!.artifacts.response).toContain("Race condition");
    expect(trace!.artifacts.errors.length).toBe(1);
    expect(trace!.artifacts.errors[0]).toContain("concurrent cache.set");

    expect(trace!.hardware).toBeTruthy();
    expect(trace!.hardware!.processor).toBe("Apple M3 Pro");
  });

  // ── Trace list filtering ──────────────────────────────────

  it("loadTraceList returns all entries when no filters", async () => {
    const entries = await loadTraceList();
    expect(entries.length).toBe(2);
  });

  it("loadTraceList filters by model (case-insensitive partial)", async () => {
    const entries = await loadTraceList({ model: "gemma" });
    expect(entries.length).toBe(1);
    expect(entries[0].trace_id).toBe("trace-nestjs-jwt");
    expect(entries[0].model).toBe("google/gemma-4-e4b");
  });

  it("loadTraceList filters by status", async () => {
    const entries = await loadTraceList({ status: "failed" });
    expect(entries.length).toBe(1);
    expect(entries[0].trace_id).toBe("trace-debug-race");
    expect(entries[0].status).toBe("failed");
  });

  it("loadTraceList combines model and status filters", async () => {
    const entries = await loadTraceList({
      model: "lfm",
      status: "failed",
    });
    expect(entries.length).toBe(1);
    expect(entries[0].trace_id).toBe("trace-debug-race");
  });

  it("loadTraceList returns empty array when no matches", async () => {
    const entries = await loadTraceList({ model: "nonexistent" });
    expect(entries.length).toBe(0);
  });

  it("loadTraceList with limit and offset", async () => {
    const entries = await loadTraceList({ limit: 1, offset: 1 });
    expect(entries.length).toBe(1);
  });

  // ── mapTraceToRun ─────────────────────────────────────────

  it("mapTraceToRun converts TraceData to TraceRun shape", () => {
    const data = traceDataFixtures["trace-nestjs-jwt"];
    const run = mapTraceToRun(data);

    expect(run.id).toBe("trace-nestjs-jwt");
    expect(run.model).toBe("google/gemma-4-e4b");
    expect(run.pack).toBe("nestjs-pack");
    expect(run.status).toBe("completed");
    expect(run.totalTimeMs).toBe(4820);
    expect(run.steps.length).toBe(5);
  });

  it("mapTraceToRun truncates long prompts", () => {
    const data = {
      ...traceDataFixtures["trace-nestjs-jwt"],
      prompt: "A".repeat(200),
    };
    const run = mapTraceToRun(data);
    expect(run.prompt.length).toBeLessThanOrEqual(100);
  });

  it("mapTraceToRun preserves step types, labels, and timing", () => {
    const data = traceDataFixtures["trace-nestjs-jwt"];
    const run = mapTraceToRun(data);

    expect(run.steps[0].type).toBe("system");
    expect(run.steps[0].label).toBe("System Instruction");
    expect(run.steps[1].type).toBe("tool_call");
    expect(run.steps[1].tool).toBe("prisma_user_service");
    expect(run.steps[2].type).toBe("reasoning");
    expect(run.steps[4].type).toBe("response");
  });

  it("mapTraceToRun maps failed status correctly", () => {
    const data = traceDataFixtures["trace-debug-race"];
    const run = mapTraceToRun(data);
    expect(run.status).toBe("failed");
    // Verify error step is preserved
    const errorSteps = run.steps.filter((s) => s.type === "error");
    expect(errorSteps.length).toBe(1);
    expect(errorSteps[0].status).toBe("failure");
  });

  // ── TraceTimeline renders trace data ───────────────────────

  it("TraceTimeline renders trace runs from mapped data", async () => {
    const manifest = await loadTraceManifest();
    const realTraceIds = manifest.traces.map((t) => t.trace_id);

    // Load all traces and map to TraceRun
    const settled = await Promise.allSettled(
      realTraceIds.map((id) => loadTrace(id)),
    );
    const traceRuns = settled
      .filter(
        (r): r is PromiseFulfilledResult<TraceData | null> =>
          r.status === "fulfilled",
      )
      .filter((r) => r.value !== null)
      .map((r) => mapTraceToRun(r.value!));

    render(<TraceTimeline traces={traceRuns} />);

    // Both models should appear in the sidebar
    expect(screen.getAllByText("google/gemma-4-e4b").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("lfm2.5-8b-a1b").length).toBeGreaterThanOrEqual(1);

    // Sidebar IDs
    expect(screen.getByText("trace-nestjs-jwt")).toBeTruthy();
    expect(screen.getByText("trace-debug-race")).toBeTruthy();
  });

  it("TraceTimeline shows step details from real trace data", async () => {
    const trace = await loadTrace("trace-nestjs-jwt");
    const traceRuns = [mapTraceToRun(trace!)];

    render(<TraceTimeline traces={traceRuns} />);

    // Step labels from fixture
    expect(screen.getByText("System Instruction")).toBeTruthy();
    expect(screen.getByText("Calling: prisma.user.findUnique")).toBeTruthy();
    expect(screen.getByText("Analyzing schema relations")).toBeTruthy();
    expect(screen.getByText("Generated Implementation")).toBeTruthy();
  });

  it("TraceTimeline shows correct step count from fixture", async () => {
    const trace = await loadTrace("trace-nestjs-jwt");
    const traceRuns = [mapTraceToRun(trace!)];

    render(<TraceTimeline traces={traceRuns} />);

    // 5 steps in the fixture
    expect(screen.getByText("1 / 5 steps")).toBeTruthy();
  });

  it("TraceTimeline shows failed trace with error step", async () => {
    const trace = await loadTrace("trace-debug-race");
    const traceRuns = [mapTraceToRun(trace!)];

    render(<TraceTimeline traces={traceRuns} />);

    // Error step from failed trace
    expect(screen.getByText("Error: Race condition unresolved")).toBeTruthy();
    // Status in sidebar: "cancel" icon (material for failed)
    expect(screen.getByText("cancel")).toBeTruthy();
  });

  it("TraceTimeline renders total time from fixture", async () => {
    const trace = await loadTrace("trace-nestjs-jwt");
    const traceRuns = [mapTraceToRun(trace!)];

    render(<TraceTimeline traces={traceRuns} />);

    expect(screen.getByText("4820ms")).toBeTruthy();
  });

  // ── Pipeline: empty manifest fallback ─────────────────────

  it("loadTraceManifest returns empty manifest on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network down"));

    const manifest = await loadTraceManifest();
    expect(manifest.version).toBe("1.0.0");
    expect(manifest.total_traces).toBe(0);
    expect(manifest.traces.length).toBe(0);
  });

  it("loadTrace returns null on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network down"));

    const trace = await loadTrace("any-id");
    expect(trace).toBeNull();
  });

  it("loadTraceList returns empty array on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network down"));

    const entries = await loadTraceList();
    expect(entries).toEqual([]);
  });

  // ── Pipeline: non-ok fetch responses ──────────────────────

  it("loadTraceManifest handles non-ok fetch response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: "server error" }),
    });

    const manifest = await loadTraceManifest();
    expect(manifest.total_traces).toBe(0);
  });

  it("loadTrace handles 404 response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: "not found" }),
    });

    const trace = await loadTrace("missing");
    expect(trace).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════
// REPLAYS FIXTURES
// ═══════════════════════════════════════════════════════════════════

const replayIndexFixtures: ReplayIndexEntry[] = [
  {
    run_id: "run-abc-123",
    model: "qwen3.5-9b-coder",
    workload: "nestjs-api",
    provider: "lm-studio",
    started_at: "2026-06-02T10:30:00Z",
    event_count: 5,
    file: "run-abc-123.json",
  },
  {
    run_id: "run-def-456",
    model: "llama3.2-3b",
    workload: "",
    provider: "ollama",
    started_at: "2026-06-02T09:00:00Z",
    event_count: 3,
    file: "run-def-456.json",
  },
];

const replayDataFixtures: Record<string, ReplayData> = {
  "run-abc-123": {
    version: "1.0.0",
    generated_at: "2026-06-02T10:30:05Z",
    run_id: "run-abc-123",
    model: "qwen3.5-9b-coder",
    workload: "nestjs-api",
    provider: "lm-studio",
    started_at: "2026-06-02T10:30:00Z",
    event_count: 5,
    events: [
      {
        _event_type: "RunLifecycleEvent",
        status: "started",
        model: "qwen3.5-9b-coder",
        run_id: "run-abc-123",
        timestamp: "2026-06-02T10:30:00Z",
      },
      {
        _event_type: "TokenGeneratedEvent",
        token: "Hello",
        index: 0,
        timing_ms: 12.5,
        model: "qwen3.5-9b-coder",
        run_id: "run-abc-123",
        timestamp: "2026-06-02T10:30:01Z",
      },
      {
        _event_type: "TokenGeneratedEvent",
        token: " world",
        index: 1,
        timing_ms: 15.2,
        model: "qwen3.5-9b-coder",
        run_id: "run-abc-123",
        timestamp: "2026-06-02T10:30:01.1Z",
      },
      {
        _event_type: "MetricEvent",
        name: "score",
        value: 0.92,
        model: "qwen3.5-9b-coder",
        run_id: "run-abc-123",
        timestamp: "2026-06-02T10:30:02Z",
      },
      {
        _event_type: "RunLifecycleEvent",
        status: "completed",
        model: "qwen3.5-9b-coder",
        run_id: "run-abc-123",
        duration_ms: 5000,
        timestamp: "2026-06-02T10:30:05Z",
      },
    ],
  },
  "run-def-456": {
    version: "1.0.0",
    generated_at: "2026-06-02T09:00:02Z",
    run_id: "run-def-456",
    model: "llama3.2-3b",
    workload: "",
    provider: "ollama",
    started_at: "2026-06-02T09:00:00Z",
    event_count: 3,
    events: [
      {
        _event_type: "RunLifecycleEvent",
        status: "started",
        model: "llama3.2-3b",
        run_id: "run-def-456",
        timestamp: "2026-06-02T09:00:00Z",
      },
      {
        _event_type: "TokenGeneratedEvent",
        token: "Hi",
        index: 0,
        timing_ms: 8.1,
        model: "llama3.2-3b",
        run_id: "run-def-456",
        timestamp: "2026-06-02T09:00:01Z",
      },
      {
        _event_type: "RunLifecycleEvent",
        status: "completed",
        model: "llama3.2-3b",
        run_id: "run-def-456",
        duration_ms: 2000,
        timestamp: "2026-06-02T09:00:02Z",
      },
    ],
  },
};

// ═══════════════════════════════════════════════════════════════════
// REPLAYS END-TO-END PIPELINE TESTS
// ═══════════════════════════════════════════════════════════════════

describe("Replays E2E — mocked fetch → loadReplayManifest → loadReplay → ReplayViewer", () => {
  beforeEach(() => {
    // jsdom doesn't implement scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();

    // Mock fetch for browser-mode replay loading.
    // loadReplayManifest → GET /api/replays
    // loadReplay → GET /api/replays/{run_id}
    // loadReplayList → GET /api/replays?model=...
    global.fetch = vi.fn().mockImplementation((url: string) => {
      const urlStr = String(url);

      // Replay manifest (list): GET /api/replays
      if (urlStr === "/api/replays") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(replayIndexFixtures),
        });
      }

      // Single replay: GET /api/replays/{run_id}
      const singleMatch = urlStr.match(/^\/api\/replays\/(.+)$/);
      if (singleMatch) {
        const runId = decodeURIComponent(singleMatch[1]);
        const data = replayDataFixtures[runId];
        if (data) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(data),
          });
        }
        return Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ error: "not found" }),
        });
      }

      // Replay list with query params: /api/replays?model=...
      if (urlStr.startsWith("/api/replays?")) {
        const params = new URL(urlStr, "http://localhost").searchParams;
        let filtered = [...replayIndexFixtures];
        const model = params.get("model");
        const limit = parseInt(params.get("limit") || "", 10) || undefined;
        const offset = parseInt(params.get("offset") || "", 10) || 0;
        if (model) {
          filtered = filtered.filter((r) =>
            r.model.toLowerCase().includes(model.toLowerCase()),
          );
        }
        // Sort by started_at descending (matches filterManifest behavior)
        filtered.sort(
          (a, b) =>
            new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
        );
        const sliced =
          limit !== undefined
            ? filtered.slice(offset, offset + limit)
            : filtered.slice(offset);
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(sliced),
        });
      }

      return Promise.reject(new Error(`Unmocked URL: ${urlStr}`));
    });
  });

  // ── Manifest loading ──────────────────────────────────────

  it("loadReplayManifest fetches from /api/replays and returns manifest", async () => {
    const manifest = await loadReplayManifest();
    expect(manifest.total_replays).toBe(2);
    expect(manifest.replays.length).toBe(2);
    expect(global.fetch).toHaveBeenCalledWith("/api/replays");
  });

  it("loadReplayManifest entries have correct fields", async () => {
    const manifest = await loadReplayManifest();
    const entry = manifest.replays[0];
    expect(entry.run_id).toBe("run-abc-123");
    expect(entry.model).toBe("qwen3.5-9b-coder");
    expect(entry.workload).toBe("nestjs-api");
    expect(entry.event_count).toBe(5);
  });

  // ── Single replay loading ─────────────────────────────────

  it("loadReplay returns a single replay by run_id", async () => {
    const replay = await loadReplay("run-abc-123");
    expect(replay).not.toBeNull();
    expect(replay!.run_id).toBe("run-abc-123");
    expect(replay!.model).toBe("qwen3.5-9b-coder");
    expect(replay!.events.length).toBe(5);
  });

  it("loadReplay returns full event data with types and timing", async () => {
    const replay = await loadReplay("run-abc-123");
    expect(replay).not.toBeNull();
    const events = replay!.events;

    expect(events[0]._event_type).toBe("RunLifecycleEvent");
    expect(events[0].status).toBe("started");

    expect(events[1]._event_type).toBe("TokenGeneratedEvent");
    expect(events[1].token).toBe("Hello");
    expect(events[1].timing_ms).toBe(12.5);

    expect(events[2]._event_type).toBe("TokenGeneratedEvent");
    expect(events[2].token).toBe(" world");

    expect(events[3]._event_type).toBe("MetricEvent");
    expect(events[3].name).toBe("score");
    expect(events[3].value).toBe(0.92);

    expect(events[4]._event_type).toBe("RunLifecycleEvent");
    expect(events[4].status).toBe("completed");
    expect(events[4].duration_ms).toBe(5000);
  });

  it("loadReplay returns null for non-existent run_id", async () => {
    const replay = await loadReplay("nonexistent-run");
    expect(replay).toBeNull();
  });

  it("loadReplay returns second replay with different data", async () => {
    const replay = await loadReplay("run-def-456");
    expect(replay).not.toBeNull();
    expect(replay!.model).toBe("llama3.2-3b");
    expect(replay!.events.length).toBe(3);
    expect(replay!.events[1]._event_type).toBe("TokenGeneratedEvent");
    expect(replay!.events[1].token).toBe("Hi");
  });

  // ── Replay list filtering ─────────────────────────────────

  it("loadReplayList returns all entries when no filters", async () => {
    const entries = await loadReplayList();
    expect(entries.length).toBe(2);
  });

  it("loadReplayList filters by model (case-insensitive partial)", async () => {
    const entries = await loadReplayList({ model: "qwen" });
    expect(entries.length).toBe(1);
    expect(entries[0].run_id).toBe("run-abc-123");
    expect(entries[0].model).toBe("qwen3.5-9b-coder");
  });

  it("loadReplayList returns empty array when no model match", async () => {
    const entries = await loadReplayList({ model: "nonexistent" });
    expect(entries.length).toBe(0);
  });

  it("loadReplayList with limit and offset", async () => {
    const entries = await loadReplayList({ limit: 1, offset: 1 });
    expect(entries.length).toBe(1);
    expect(entries[0].run_id).toBe("run-def-456");
  });

  // ── ReplayViewer renders from fetched data ─────────────────

  it("ReplayViewer renders sidebar from manifest fetched via network", async () => {
    render(<ReplayViewer />);

    await vi.waitFor(() => {
      expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
      expect(screen.getByText("llama3.2-3b")).toBeInTheDocument();
      expect(screen.getByText("nestjs-api")).toBeInTheDocument();
    });

    expect(global.fetch).toHaveBeenCalledWith("/api/replays");
  });

  it("ReplayViewer loads and displays replay detail on selection", async () => {
    render(<ReplayViewer />);

    // Wait for sidebar to render
    await vi.waitFor(() => {
      expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
    });

    // Click the first replay entry to load detail
    await userEvent.click(screen.getAllByText("qwen3.5-9b-coder")[0]);

    // Wait for the detail to load — event type chips appear in the timeline
    await vi.waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
    });

    // Verify fetch was called for the detail endpoint
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/replays/" + encodeURIComponent("run-abc-123"),
    );

    // Verify event types appear in the rendered timeline
    expect(screen.getAllByText("Run Lifecycle").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Token Generated").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Metric")).toBeInTheDocument();
  });

  it("ReplayViewer shows header metadata after loading replay data", async () => {
    render(<ReplayViewer />);

    await vi.waitFor(() => {
      expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
    });

    await userEvent.click(screen.getAllByText("qwen3.5-9b-coder")[0]);

    await vi.waitFor(() => {
      // Header shows model name (also in sidebar, hence getAllByText)
      expect(screen.getAllByText("qwen3.5-9b-coder").length).toBeGreaterThanOrEqual(2);
      // Workload chip in header
      expect(screen.getAllByText("nestjs-api").length).toBeGreaterThanOrEqual(2);
      // run_id in header
      expect(screen.getByText("run-abc-123")).toBeInTheDocument();
    });
  });

  it("ReplayViewer renders playback controls after pipeline load", async () => {
    render(<ReplayViewer />);

    await vi.waitFor(() => {
      expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
    });

    await userEvent.click(screen.getAllByText("qwen3.5-9b-coder")[0]);

    await vi.waitFor(() => {
      expect(screen.getByLabelText("Previous event")).toBeInTheDocument();
      expect(screen.getByLabelText("Play")).toBeInTheDocument();
      expect(screen.getByLabelText("Next event")).toBeInTheDocument();
      expect(screen.getByText("1 / 5 events")).toBeInTheDocument();
    });
  });

  it("ReplayViewer shows active sidebar highlighting after selection", async () => {
    render(<ReplayViewer />);

    await vi.waitFor(() => {
      expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
    });

    await userEvent.click(screen.getAllByText("qwen3.5-9b-coder")[0]);

    await vi.waitFor(() => {
      const sidebarItems = document.querySelectorAll(".rpv-sidebar-item");
      expect(sidebarItems.length).toBe(2);
      expect(sidebarItems[0].classList.contains("rpv-sidebar-active")).toBe(true);
      expect(sidebarItems[1].classList.contains("rpv-sidebar-active")).toBe(false);
    });
  });

  // ── Pipeline: error handling ──────────────────────────────

  it("loadReplayManifest returns empty manifest on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network down"));

    const manifest = await loadReplayManifest();
    expect(manifest.total_replays).toBe(0);
    expect(manifest.replays.length).toBe(0);
  });

  it("loadReplay returns null on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network down"));

    const replay = await loadReplay("any-id");
    expect(replay).toBeNull();
  });

  it("loadReplayList returns empty array on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network down"));

    const entries = await loadReplayList();
    expect(entries).toEqual([]);
  });

  it("loadReplayManifest returns empty manifest on non-ok response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: "server error" }),
    });

    const manifest = await loadReplayManifest();
    expect(manifest.total_replays).toBe(0);
  });

  it("loadReplay handles 404 response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: "not found" }),
    });

    const replay = await loadReplay("missing");
    expect(replay).toBeNull();
  });

  it("ReplayViewer shows empty state when manifest fetch fails (graceful degradation)", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network down"));

    render(<ReplayViewer />);

    await vi.waitFor(() => {
      expect(screen.getByText("No replay sessions found.")).toBeInTheDocument();
      expect(screen.queryByText("Loading replays…")).not.toBeInTheDocument();
    });
  });

  it("ReplayViewer shows error when detail fetch fails", async () => {
    // First call (manifest) succeeds, second call (detail) fails
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(replayIndexFixtures),
        });
      }
      return Promise.reject(new Error("Server error"));
    });

    render(<ReplayViewer />);

    // Wait for sidebar to appear
    await vi.waitFor(() => {
      expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
    });

    // Click to trigger detail load (which will fail)
    await userEvent.click(screen.getAllByText("qwen3.5-9b-coder")[0]);

    await vi.waitFor(() => {
      expect(screen.getByText(/Replay.*not found/)).toBeInTheDocument();
    });
  });

  it("ReplayViewer shows not-found error when detail returns 404", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      const urlStr = String(url);
      if (urlStr === "/api/replays") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(replayIndexFixtures),
        });
      }
      // Return 404 for any detail request
      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: "not found" }),
      });
    });

    render(<ReplayViewer />);

    await vi.waitFor(() => {
      expect(screen.getByText("qwen3.5-9b-coder")).toBeInTheDocument();
    });

    await userEvent.click(screen.getAllByText("qwen3.5-9b-coder")[0]);

    await vi.waitFor(() => {
      expect(screen.getByText(/Replay.*not found/)).toBeInTheDocument();
    });
  });
});

// ═══════════════════════════════════════════════════════════════════
// BENCHMARK LIFECYCLE VIA SSE — RunBenchmarkButton → ReplayToast
// ═══════════════════════════════════════════════════════════════════

describe("Benchmark lifecycle via SSE — start → lifecycle event → ReplayToast", () => {
  // ── Mock EventSource ──────────────────────────────────────────
  let mockEventSourceRegistry: {
    onmessage: ((event: MessageEvent) => void) | null;
    onerror: (() => void) | null;
    close: ReturnType<typeof vi.fn>;
  } | null = null;

  class MockEventSource {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSED = 2;
    CONNECTING = 0;
    OPEN = 1;
    CLOSED = 2;
    readyState = 1;
    url = "";
    withCredentials = false;
    onopen: (() => void) | null = null;
    close = vi.fn();
    addEventListener = vi.fn();
    removeEventListener = vi.fn();
    dispatchEvent = vi.fn();

    constructor(url: string) {
      this.url = url;
      const reg = {
        onmessage: null as ((event: MessageEvent) => void) | null,
        onerror: null as (() => void) | null,
        close: this.close,
      };
      mockEventSourceRegistry = reg;

      Object.defineProperty(this, "onmessage", {
        get: () => reg.onmessage,
        set: (fn) => {
          reg.onmessage = fn;
        },
        configurable: true,
      });

      Object.defineProperty(this, "onerror", {
        get: () => reg.onerror,
        set: (fn) => {
          reg.onerror = fn;
        },
        configurable: true,
      });
    }
  }

  function sendSSEEvent(data: Record<string, unknown>) {
    if (mockEventSourceRegistry?.onmessage) {
      mockEventSourceRegistry.onmessage({
        data: JSON.stringify(data),
      } as MessageEvent);
    }
  }

  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("EventSource", MockEventSource);
    vi.useFakeTimers({ shouldAdvanceTime: true });

    // Mock fetch for the full benchmark lifecycle:
    // 1. GET /api/status → connected (open modal)
    // 2. POST /api/run-benchmark → starts benchmark
    global.fetch = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      const urlStr = String(url);

      if (urlStr === "/api/status") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({ connected: true, models: ["qwen3.5-9b-coder"] }),
        });
      }

      if (urlStr === "/api/run-benchmark" && options?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({ success: true, pid: 99999, message: "Benchmark started" }),
        });
      }

      // POST /api/run-benchmark/logs?pid=99999 (polled by component)
      if (urlStr.startsWith("/api/run-benchmark/logs")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({ pid: 99999, status: "running", stdout: "SSE_PORT:9090\n", stderr: "" }),
        });
      }

      return Promise.reject(new Error(`Unmocked URL: ${urlStr}`));
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    mockEventSourceRegistry = null;
  });

  it("shows ReplayToast after starting a benchmark and receiving a completed lifecycle event", async () => {
    const user = userEvent.setup();

    render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
      </>,
    );

    // ── Step 1: Open the benchmark dialog ─────────────────────
    await user.click(screen.getByText("Run new benchmark"));

    await vi.waitFor(() => {
      expect(screen.getByText("Run New Benchmark")).toBeInTheDocument();
    });

    // ── Step 2: Wait for connection status ───────────────────
    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    // ── Step 3: Click "Run Benchmark" to start ───────────────
    await user.click(screen.getByText("Run Benchmark"));

    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
      expect(screen.getByText(/PID 99999/)).toBeInTheDocument();
    });

    // ── Step 4: Send a completed lifecycle event via SSE ─────
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-bench-integration-1",
      duration_ms: 5000,
    });

    // ── Step 5: Verify ReplayToast appears ───────────────────
    // Model name appears in both the modal's model list (<code>) and the
    // toast (<strong>), so use getAllByText and check at least 2 matches.
    await vi.waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
      const modelMatches = screen.getAllByText(/qwen3.5-9b-coder/);
      expect(modelMatches.length).toBeGreaterThanOrEqual(2);
    });

    // ── Step 6: Verify the toast links to the replay ─────────
    const link = screen.getByRole("status").closest("a");
    expect(link?.getAttribute("href")).toBe(
      "/replays?run_id=run-bench-integration-1",
    );

    // ── Step 7: Verify toast auto-dismisses after 6s ─────────
    act(() => {
      vi.advanceTimersByTime(6000);
    });

    await vi.waitFor(() => {
      expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();
    });
  });

  it("shows ReplayToast with 'failed' status when benchmark fails", async () => {
    const user = userEvent.setup();

    render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
      </>,
    );

    await user.click(screen.getByText("Run new benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("Run Benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
    });

    // Send a failed lifecycle event
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "failed",
      model: "qwen3.5-9b-coder",
      run_id: "run-bench-fail-1",
    });

    await vi.waitFor(() => {
      expect(screen.getByText("Replay failed")).toBeInTheDocument();
      // The toast description includes the status text "failed"
      expect(screen.getByText(/— failed$/)).toBeInTheDocument();
    });
  });

  it("does not show ReplayToast when benchmark is still running (no completed event)", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
      </>,
    );

    await user.click(screen.getByText("Run new benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("Run Benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
    });

    // Send only a "started" lifecycle event (not completed/failed)
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "started",
      model: "qwen3.5-9b-coder",
      run_id: "run-bench-started-1",
    });

    // ReplayToast should NOT appear for started events
    await vi.waitFor(() => {
      expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();
      expect(screen.queryByText("Replay failed")).not.toBeInTheDocument();
    });
  });

  it("supports multiple benchmarks: second completion shows separate toast", async () => {
    const user = userEvent.setup();

    render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
      </>,
    );

    // Start and complete first benchmark
    await user.click(screen.getByText("Run new benchmark"));

    // Close the dialog after first benchmark completes
    // First we need to interact with the modal

    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("Run Benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
    });

    // Send completion for first benchmark
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "model-a",
      run_id: "run-multi-a",
    });

    await vi.waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
      expect(screen.getByText(/model-a/)).toBeInTheDocument();
    });

    // Dismiss toast by advancing past auto-dismiss
    act(() => {
      vi.advanceTimersByTime(6000);
    });

    await vi.waitFor(() => {
      expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();
    });

    // Send completion for second benchmark (different run_id)
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "model-b",
      run_id: "run-multi-b",
    });

    await vi.waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
      expect(screen.getByText(/model-b/)).toBeInTheDocument();
    });
  });

  it("shows ReplayToast after SSE connection drops and reconnects mid-benchmark", async () => {
    const user = userEvent.setup();

    render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
      </>,
    );

    // ── Step 1: Open dialog, connect, start benchmark ──────────
    await user.click(screen.getByText("Run new benchmark"));

    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("Run Benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
    });

    // No toast before any lifecycle event
    expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();

    // ── Step 2: Simulate SSE connection drop ─────────────────
    // The native EventSource auto-reconnects internally;
    // onerror fires but the onmessage handler stays registered.
    act(() => {
      mockEventSourceRegistry?.onerror?.();
    });

    // Still no toast (no completion event yet)
    expect(screen.queryByText("Replay recorded")).not.toBeInTheDocument();

    // ── Step 3: Simulate events arriving after reconnection ───
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "recon-test-1",
      duration_ms: 5000,
    });

    // ── Step 4: Toast should still fire after reconnect ───────
    await vi.waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
      const modelMatches = screen.getAllByText(/qwen3.5-9b-coder/);
      expect(modelMatches.length).toBeGreaterThanOrEqual(2);
    });

    // Verify the toast links to the replay and contains the run_id
    const toastEl = screen.getByRole("status");
    const link = toastEl.closest("a");
    expect(link?.getAttribute("href")).toBe(
      "/replays?run_id=recon-test-1",
    );
    expect(toastEl.textContent).toContain("recon-test-1");
  });

  it("keeps ReplayToast visible after SSE connection drops post-completion", async () => {
    const user = userEvent.setup();

    render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
      </>,
    );

    // ── Step 1: Open dialog, connect, start benchmark ──────────
    await user.click(screen.getByText("Run new benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("Run Benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
    });

    // ── Step 2: Send completion event → toast appears ─────────
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-survive-1",
      duration_ms: 5000,
    });

    await vi.waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
    });

    // Grab the toast element reference now so we can check it survives
    const toastEl = screen.getByRole("status");
    expect(toastEl.textContent).toContain("qwen3.5-9b-coder");
    expect(toastEl.textContent).toContain("run-survive");

    const link = toastEl.closest("a");
    expect(link?.getAttribute("href")).toBe("/replays?run_id=run-survive-1");

    // ── Step 3: Drop SSE connection ─────────────────────────
    act(() => {
      mockEventSourceRegistry?.onerror?.();
    });

    // ── Step 4: Toasts still visible after disconnect ────────
    expect(screen.getByText("Replay recorded")).toBeInTheDocument();
    expect(toastEl.textContent).toContain("qwen3.5-9b-coder");
    expect(toastEl.textContent).toContain("run-survive");

    // Link href is unchanged
    expect(link?.getAttribute("href")).toBe("/replays?run_id=run-survive-1");

    // The toast is still interactive (has the arrow icon)
    expect(toastEl.textContent).toContain("arrow_forward");
  });

  it("does not duplicate toasts during multiple rapid SSE reconnections", async () => {
    const user = userEvent.setup();

    render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
      </>,
    );

    // ── Step 1: Open dialog, connect, start benchmark ──────────
    await user.click(screen.getByText("Run new benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("Run Benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
    });

    // ── Step 2: Send completed event → toast appears once ──────
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-rapid-1",
      duration_ms: 5000,
    });

    await vi.waitFor(() => {
      expect(screen.getByText("Replay recorded")).toBeInTheDocument();
    });

    // Exactly one toast in the DOM
    expect(screen.getAllByRole("status").length).toBe(1);

    // ── Step 3: Rapid reconnect cycle × 3 ─────────────────────
    // Each cycle: drop connection → same completed event re-arrives
    // The notifiedRunIds ref should prevent duplicate toasts.
    for (let i = 0; i < 3; i++) {
      act(() => {
        mockEventSourceRegistry?.onerror?.();
      });

      // Same run_id arrives again on the reconnected stream
      sendSSEEvent({
        _event_type: "RunLifecycleEvent",
        status: "completed",
        model: "qwen3.5-9b-coder",
        run_id: "run-rapid-1",
        duration_ms: 5000,
      });

      // Still exactly one toast (deduplication worked)
      await vi.waitFor(() => {
        expect(screen.getAllByRole("status").length).toBe(1);
      });
    }

    // ── Step 4: Verify the original toast content is intact ───
    const toastEl = screen.getByRole("status");
    expect(toastEl.textContent).toContain("Replay recorded");
    expect(toastEl.textContent).toContain("qwen3.5-9b-coder");
    expect(toastEl.textContent).toContain("run-rapid-1");
    expect(toastEl.textContent).toContain("arrow_forward");

    const link = toastEl.closest("a");
    expect(link?.getAttribute("href")).toBe("/replays?run_id=run-rapid-1");

    // ── Step 5: New run_id after all reconnections still works ─
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-rapid-2",
      duration_ms: 4000,
    });

    await vi.waitFor(() => {
      expect(screen.getAllByRole("status").length).toBe(1);
      expect(screen.getByRole("status").textContent).toContain("run-rapid-2");
    });
  });

  it("updates ReplaySidebarBadge count after lifecycle events in the integration flow", async () => {
    const user = userEvent.setup();

    render(
      <>
        <RunBenchmarkButton />
        <ReplayToast />
        <ReplaySidebarBadge />
      </>,
    );

    // ── Step 1: Open the benchmark dialog ─────────────────────
    await user.click(screen.getByText("Run new benchmark"));

    await vi.waitFor(() => {
      expect(screen.getByText("Run New Benchmark")).toBeInTheDocument();
    });

    // ── Step 2: Wait for connection status ───────────────────
    await vi.waitFor(() => {
      expect(screen.getByText(/Connected/)).toBeInTheDocument();
    });

    // ── Step 3: Click "Run Benchmark" to start ───────────────
    await user.click(screen.getByText("Run Benchmark"));
    await vi.waitFor(() => {
      expect(screen.getByText("Benchmark started")).toBeInTheDocument();
    });

    // ── Step 4: Badge should be hidden initially (0 count) ───
    expect(screen.queryByText("1")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("1 new replays")).not.toBeInTheDocument();

    // ── Step 5: Send a completed lifecycle event via SSE ─────
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-badge-test-1",
      duration_ms: 5000,
    });

    // ── Step 6: Verify badge shows count 1 ───────────────────
    await vi.waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByLabelText("1 new replays")).toBeInTheDocument();
    });

    // ── Step 7: Send a second completed event (different run_id) ──
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-badge-test-2",
      duration_ms: 4000,
    });

    await vi.waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByLabelText("2 new replays")).toBeInTheDocument();
    });

    // ── Step 8: Send a duplicate run_id — count should NOT change ──
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "completed",
      model: "qwen3.5-9b-coder",
      run_id: "run-badge-test-2",
      duration_ms: 4000,
    });

    await vi.waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByLabelText("2 new replays")).toBeInTheDocument();
    });

    // ── Step 9: Send a failed event — should also increment ──
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "failed",
      model: "qwen3.5-9b-coder",
      run_id: "run-badge-fail-1",
    });

    await vi.waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByLabelText("3 new replays")).toBeInTheDocument();
    });

    // ── Step 10: Send a started event — should NOT increment ──
    sendSSEEvent({
      _event_type: "RunLifecycleEvent",
      status: "started",
      model: "qwen3.5-9b-coder",
      run_id: "run-badge-started-1",
    });

    await vi.waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByLabelText("3 new replays")).toBeInTheDocument();
    });
  });
});


// @vitest-environment node
import { describe, it, expect, vi, afterEach } from "vitest";
import {
  buildLeaderboard,
  groupByModel,
  aggregateFailures,
  loadCommunityResults,
  loadAllResults,
  loadResults,
} from "./loadResults";
import type {
  BenchmarkResult,
  FailureBreakdown,
  AggregatedResults,
  ModelSummary,
} from "./loadResults";

// ── Module-level mock fs with vi.hoisted() ────────────────────
// In Astro's vitest environment, import.meta.env.SSR is true, so
// loadResults/loadCommunityResults read data via fs.readFileSync.
//
// We use vi.hoisted() to create the mock function at the hoisted
// position, then capture it in the vi.mock factory closure. Tests
// reconfigure it by calling methods directly on mockReadFileSync.

const { mockReadFileSync } = vi.hoisted(() => {
  return {
    mockReadFileSync: vi.fn(() => {
      throw new Error("ENOENT: default mock");
    }) as any,
  };
});

vi.mock("fs", () => ({
  readFileSync: mockReadFileSync,
  promises: { readFile: vi.fn() },
  existsSync: vi.fn(),
  writeFileSync: vi.fn(),
}));

// ── Fixture data ──────────────────────────────────────────────

const fixtureRuns: AggregatedResults = {
  version: "1.0.0",
  generated_at: "2026-06-01T00:00:00.000Z",
  total_models: 1,
  total_runs: 1,
  runs: [
    {
      run_id: "test-run-1",
      model: "test-model",
      model_metadata: { size: "7B", quantization: "Q4_K_M" },
      hardware: {
        platform: "macOS",
        processor: "M3",
        memory_gb: 18,
        architecture: "arm64",
      },
      timestamp: "2026-06-01T00:00:00.000Z",
      git_sha: "abc123",
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
      stats: {
        mean: 0.78,
        std: 0.05,
        min: 0.73,
        max: 0.83,
        median: 0.78,
        runs: 5,
        confidence_95: [0.75, 0.81] as [number, number],
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
      config_snapshot: {},
      prompt_version: "v1",
      packs_used: [],
      seed: null,
    },
  ],
};

const communityModel = {
  model: "community-model",
  metadata: { size: "13B" },
  best_run_id: "community-run",
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
    tokens_per_sec: 45,
    normalized_tps: 42.75,
    ttft_ms: 600,
    total_latency_ms: 3500,
    memory_pressure_mb: 2000,
  },
  stats: { mean: 0.68, std: 0.05, runs: 3 },
  total_failures: 2,
};

// ── Helpers ──────────────────────────────────────────────────

function makeResult(overrides: Partial<BenchmarkResult> = {}): BenchmarkResult {
  return {
    run_id: "run-default",
    model: "default-model",
    model_metadata: { size: "7B", quantization: "Q4_K_M" },
    hardware: {
      platform: "macOS",
      processor: "M3",
      memory_gb: 18,
      architecture: "arm64",
    },
    timestamp: "2026-06-01T00:00:00.000Z",
    git_sha: "abc123",
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
    stats: {
      mean: 0.78,
      std: 0.05,
      min: 0.73,
      max: 0.83,
      median: 0.78,
      runs: 5,
      confidence_95: [0.75, 0.81] as [number, number],
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
    config_snapshot: {},
    prompt_version: "v1",
    packs_used: [],
    seed: null,
    ...overrides,
  };
}

// ═══════════════════════════════════════════════════════════════
// buildLeaderboard
// ═══════════════════════════════════════════════════════════════

describe("buildLeaderboard", () => {
  it("returns empty leaderboard for empty input", () => {
    const result = buildLeaderboard([]);
    expect(result.leaderboard).toEqual([]);
    expect(result.localCount).toBe(0);
    expect(result.generated_at).toBeTruthy();
  });

  it("handles a single model with one run", () => {
    const result = buildLeaderboard([makeResult({ model: "alpha" })]);
    expect(result.leaderboard.length).toBe(1);
    expect(result.leaderboard[0].model).toBe("alpha");
    expect(result.leaderboard[0].total_failures).toBe(0);
  });

  it("picks the best run when multiple runs exist for the same model", () => {
    const run1 = makeResult({
      model: "alpha",
      run_id: "run-1",
      metrics: { ...makeResult().metrics, overall_score: 0.6 },
    });
    const run2 = makeResult({
      model: "alpha",
      run_id: "run-2",
      metrics: { ...makeResult().metrics, overall_score: 0.9 },
    });
    const run3 = makeResult({
      model: "alpha",
      run_id: "run-3",
      metrics: { ...makeResult().metrics, overall_score: 0.7 },
    });

    const result = buildLeaderboard([run1, run2, run3]);
    expect(result.leaderboard.length).toBe(1);
    expect(result.leaderboard[0].best_run_id).toBe("run-2");
    expect(result.leaderboard[0].metrics.overall_score).toBe(0.9);
  });

  it("computes total_failures correctly by summing all failure types", () => {
    const result = makeResult({
      failures: {
        hallucinated_api: 2,
        wrong_async_usage: 3,
        incorrect_json_schema: 1,
        syntax_error: 0,
        logic_error: 5,
        type_error: 0,
        missing_import: 1,
        stale_closure: 0,
        race_condition: 2,
        incorrect_di: 0,
        oververbose: 1,
        missed_constraint: 0,
        other: 1,
      },
    });
    const leaderboard = buildLeaderboard([result]);
    expect(leaderboard.leaderboard[0].total_failures).toBe(16);
  });

  it("computes total_failures as 0 when all failures are zero", () => {
    const result = makeResult({});
    const leaderboard = buildLeaderboard([result]);
    expect(leaderboard.leaderboard[0].total_failures).toBe(0);
  });

  it("sorts models by overall score descending", () => {
    const low = makeResult({
      model: "low",
      metrics: { ...makeResult().metrics, overall_score: 0.3 },
    });
    const mid = makeResult({
      model: "mid",
      metrics: { ...makeResult().metrics, overall_score: 0.6 },
    });
    const high = makeResult({
      model: "high",
      metrics: { ...makeResult().metrics, overall_score: 0.9 },
    });

    const result = buildLeaderboard([low, mid, high]);
    expect(result.leaderboard.map((m) => m.model)).toEqual([
      "high",
      "mid",
      "low",
    ]);
  });

  it("handles ties in overall score", () => {
    const a = makeResult({
      model: "a",
      metrics: { ...makeResult().metrics, overall_score: 0.5 },
    });
    const b = makeResult({
      model: "b",
      metrics: { ...makeResult().metrics, overall_score: 0.5 },
    });

    const result = buildLeaderboard([a, b]);
    const scores = result.leaderboard.map((m) => m.metrics.overall_score);
    expect(scores).toEqual([0.5, 0.5]);
  });

  it("preserves source as 'local' for all models", () => {
    const result = buildLeaderboard([makeResult()]);
    expect(result.leaderboard[0].source).toBe("local");
  });

  it("preserves metadata from the best run", () => {
    const run1 = makeResult({
      model: "m",
      run_id: "r1",
      model_metadata: { size: "3B" },
      metrics: { ...makeResult().metrics, overall_score: 0.5 },
    });
    const run2 = makeResult({
      model: "m",
      run_id: "r2",
      model_metadata: { size: "7B" },
      metrics: { ...makeResult().metrics, overall_score: 0.9 },
    });

    const result = buildLeaderboard([run1, run2]);
    expect(result.leaderboard[0].metadata.size).toBe("7B");
  });

  it("handles models with null confidence_95", () => {
    const result = makeResult({
      stats: { ...makeResult().stats, confidence_95: null },
    });
    const leaderboard = buildLeaderboard([result]);
    expect(leaderboard.leaderboard[0].stats.runs).toBe(5);
  });

  it("includes localCount reflecting total models", () => {
    const r1 = makeResult({ model: "a" });
    const r2 = makeResult({ model: "b" });
    const result = buildLeaderboard([r1, r2]);
    expect(result.localCount).toBe(2);
  });

  it("handles models with no metadata entries", () => {
    const result = makeResult({ model_metadata: {} });
    const leaderboard = buildLeaderboard([result]);
    expect(leaderboard.leaderboard[0].metadata).toEqual({});
  });
});

// ═══════════════════════════════════════════════════════════════
// groupByModel
// ═══════════════════════════════════════════════════════════════

describe("groupByModel", () => {
  it("returns empty map for empty array", () => {
    const map = groupByModel([]);
    expect(map.size).toBe(0);
  });

  it("groups a single result correctly", () => {
    const r = makeResult({ model: "alpha", run_id: "r1" });
    const map = groupByModel([r]);
    expect(map.size).toBe(1);
    expect(map.get("alpha")).toHaveLength(1);
    expect(map.get("alpha")![0].run_id).toBe("r1");
  });

  it("groups multiple different models", () => {
    const r1 = makeResult({ model: "alpha" });
    const r2 = makeResult({ model: "beta" });
    const r3 = makeResult({ model: "gamma" });
    const map = groupByModel([r1, r2, r3]);
    expect(map.size).toBe(3);
    expect(map.get("alpha")).toHaveLength(1);
    expect(map.get("beta")).toHaveLength(1);
    expect(map.get("gamma")).toHaveLength(1);
  });

  it("groups multiple runs of the same model together", () => {
    const r1 = makeResult({ model: "alpha", run_id: "r1" });
    const r2 = makeResult({ model: "alpha", run_id: "r2" });
    const r3 = makeResult({ model: "alpha", run_id: "r3" });
    const map = groupByModel([r1, r2, r3]);
    expect(map.size).toBe(1);
    expect(map.get("alpha")).toHaveLength(3);
    expect(map.get("alpha")!.map((r) => r.run_id)).toEqual(["r1", "r2", "r3"]);
  });

  it("preserves insertion order within each model group", () => {
    const r1 = makeResult({ model: "alpha", run_id: "r1" });
    const r2 = makeResult({ model: "beta", run_id: "r2" });
    const r3 = makeResult({ model: "alpha", run_id: "r3" });
    const map = groupByModel([r1, r2, r3]);
    expect(map.get("alpha")!.map((r) => r.run_id)).toEqual(["r1", "r3"]);
  });

  it("handles model names with special characters", () => {
    const r = makeResult({ model: "facebook/llama-3.1-8b-instruct" });
    const map = groupByModel([r]);
    expect(map.size).toBe(1);
    expect(map.has("facebook/llama-3.1-8b-instruct")).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════
// aggregateFailures
// ═══════════════════════════════════════════════════════════════

describe("aggregateFailures", () => {
  it("returns empty arrays for empty input", () => {
    const result = aggregateFailures([]);
    expect(result.labels).toEqual([]);
    expect(result.counts).toEqual([]);
  });

  it("returns empty arrays when all failure counts are zero", () => {
    const r1 = makeResult({});
    const r2 = makeResult({});
    const result = aggregateFailures([r1, r2]);
    expect(result.labels).toEqual([]);
    expect(result.counts).toEqual([]);
  });

  it("aggregates failures from a single result", () => {
    const r = makeResult({
      failures: {
        hallucinated_api: 2,
        wrong_async_usage: 0,
        incorrect_json_schema: 0,
        syntax_error: 1,
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
    });
    const result = aggregateFailures([r]);
    expect(result.labels).toContain("Hallucinated API");
    expect(result.labels).toContain("Syntax Error");
    expect(result.labels).not.toContain("Logic Error");
  });

  it("aggregates failures across multiple results (sum)", () => {
    const r1 = makeResult({
      model: "a",
      failures: {
        ...makeResult().failures,
        hallucinated_api: 3,
        logic_error: 2,
      },
    });
    const r2 = makeResult({
      model: "b",
      failures: {
        ...makeResult().failures,
        hallucinated_api: 1,
        logic_error: 5,
      },
    });
    const result = aggregateFailures([r1, r2]);
    const hallucinatedIndex = result.labels.indexOf("Hallucinated API");
    const logicErrorIndex = result.labels.indexOf("Logic Error");
    expect(result.counts[hallucinatedIndex]).toBe(4);
    expect(result.counts[logicErrorIndex]).toBe(7);
  });

  it("sorts failures by count descending", () => {
    const r = makeResult({
      failures: {
        ...makeResult().failures,
        hallucinated_api: 1,
        logic_error: 5,
        syntax_error: 3,
        type_error: 2,
      },
    });
    const result = aggregateFailures([r]);
    expect(result.labels[0]).toBe("Logic Error");
    expect(result.labels[1]).toBe("Syntax Error");
    expect(result.labels[2]).toBe("Type Error");
    expect(result.labels[3]).toBe("Hallucinated API");
  });

  it("maps all failure keys to human-readable labels", () => {
    const r = makeResult({
      failures: {
        hallucinated_api: 1,
        wrong_async_usage: 1,
        incorrect_json_schema: 1,
        syntax_error: 1,
        logic_error: 1,
        type_error: 1,
        missing_import: 1,
        stale_closure: 1,
        race_condition: 1,
        incorrect_di: 1,
        oververbose: 1,
        missed_constraint: 1,
        other: 1,
      },
    });
    const result = aggregateFailures([r]);
    expect(result.labels).toContain("Hallucinated API");
    expect(result.labels).toContain("Wrong Async");
    expect(result.labels).toContain("Bad JSON Schema");
    expect(result.labels).toContain("Syntax Error");
    expect(result.labels).toContain("Logic Error");
    expect(result.labels).toContain("Type Error");
    expect(result.labels).toContain("Missing Import");
    expect(result.labels).toContain("Stale Closure");
    expect(result.labels).toContain("Race Condition");
    expect(result.labels).toContain("Bad DI");
    expect(result.labels).toContain("Oververbose");
    expect(result.labels).toContain("Missed Constraint");
    expect(result.labels).toContain("Other");
    expect(result.labels.length).toBe(13);
  });

  it("uses raw key as label fallback when no mapping exists", () => {
    const r = makeResult({
      failures: {
        ...makeResult().failures,
        unknown_error: 5,
      } as unknown as FailureBreakdown,
    });
    const result = aggregateFailures([r]);
    expect(result.labels).toContain("unknown_error");
  });

  it("handles partial zero-count failures correctly", () => {
    const r1 = makeResult({
      model: "a",
      failures: { ...makeResult().failures, logic_error: 3, syntax_error: 0 },
    });
    const r2 = makeResult({
      model: "b",
      failures: { ...makeResult().failures, logic_error: 0, syntax_error: 4 },
    });
    const result = aggregateFailures([r1, r2]);
    expect(result.labels).toContain("Logic Error");
    expect(result.labels).toContain("Syntax Error");
    const logicIndex = result.labels.indexOf("Logic Error");
    const syntaxIndex = result.labels.indexOf("Syntax Error");
    expect(result.counts[logicIndex]).toBe(3);
    expect(result.counts[syntaxIndex]).toBe(4);
  });

  it("handles a single model with one failure type", () => {
    const r = makeResult({
      failures: { ...makeResult().failures, race_condition: 7 },
    });
    const result = aggregateFailures([r]);
    expect(result.labels).toEqual(["Race Condition"]);
    expect(result.counts).toEqual([7]);
  });
});

// ═══════════════════════════════════════════════════════════════
// loadCommunityResults
// ═══════════════════════════════════════════════════════════════

describe("loadCommunityResults", () => {
  afterEach(() => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
  });

  it("returns community models with source='community' when leaderboard.json has data", async () => {
    mockReadFileSync.mockReturnValue(
      JSON.stringify({ models: [communityModel] }),
    );
    const result = await loadCommunityResults();
    expect(result.length).toBe(1);
    expect(result[0].model).toBe("community-model");
    expect(result[0].source).toBe("community");
    expect(result[0].total_failures).toBe(2);
  });

  it("returns empty array when leaderboard.json has empty models", async () => {
    mockReadFileSync.mockReturnValue(JSON.stringify({ models: [] }));
    const result = await loadCommunityResults();
    expect(result).toEqual([]);
  });

  it("returns empty array when leaderboard.json has no models field", async () => {
    mockReadFileSync.mockReturnValue(JSON.stringify({}));
    const result = await loadCommunityResults();
    expect(result).toEqual([]);
  });

  it("returns empty array when file read fails", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadCommunityResults();
    expect(result).toEqual([]);
  });

  it("preserves all model fields from the response", async () => {
    const detailedModel = {
      model: "m1",
      metadata: { size: "7B" },
      best_run_id: "r1",
      metrics: {
        coding_score: 0.9,
        reasoning_score: 0.8,
        instruction_score: 0.85,
        frontend_score: 0.75,
        math_score: 0.7,
        debugging_score: 0.65,
        overall_score: 0.82,
      },
      performance: {
        tokens_per_sec: 60,
        normalized_tps: 57,
        ttft_ms: 400,
        total_latency_ms: 3000,
        memory_pressure_mb: 1400,
      },
      stats: { mean: 0.82, std: 0.05, runs: 5 },
      total_failures: 3,
    };
    mockReadFileSync.mockReturnValue(
      JSON.stringify({ models: [detailedModel] }),
    );
    const result = await loadCommunityResults();
    expect(result[0].metrics.overall_score).toBe(0.82);
    expect(result[0].performance.tokens_per_sec).toBe(60);
    expect(result[0].stats.runs).toBe(5);
  });
});

// ═══════════════════════════════════════════════════════════════
// loadAllResults
// Tests the merge/dedup/sort logic by injecting fake loader
// functions so we bypass the filesystem entirely.
// ═══════════════════════════════════════════════════════════════

describe("loadAllResults", () => {
  it("merges local and community results into a single leaderboard", async () => {
    const result = await loadAllResults(
      async () => fixtureRuns.runs,
      async () => [{ ...communityModel, source: "community" } as ModelSummary],
    );
    expect(result.leaderboard.length).toBe(2);
    expect(result.localCount).toBe(1);
    expect(result.communityCount).toBe(1);
  });

  it("assigns source correctly: 'local' vs 'community'", async () => {
    const result = await loadAllResults(
      async () => fixtureRuns.runs,
      async () => [{ ...communityModel, source: "community" } as ModelSummary],
    );
    const localModel = result.leaderboard.find((m) => m.model === "test-model");
    const communityFound = result.leaderboard.find(
      (m) => m.model === "community-model",
    );
    expect(localModel?.source).toBe("local");
    expect(communityFound?.source).toBe("community");
  });

  it("deduplicates: local model takes precedence over community with same name", async () => {
    const result = await loadAllResults(
      async () => fixtureRuns.runs,
      async () => [
        {
          ...communityModel,
          model: "test-model",
          source: "community",
        } as ModelSummary,
      ],
    );
    expect(result.leaderboard.length).toBe(1);
    expect(result.localCount).toBe(1);
    expect(result.communityCount).toBe(0);
    expect(result.leaderboard[0].source).toBe("local");
  });

  it("handles no community results", async () => {
    const result = await loadAllResults(
      async () => fixtureRuns.runs,
      async () => [],
    );
    expect(result.leaderboard.length).toBe(1);
    expect(result.localCount).toBe(1);
    expect(result.communityCount).toBe(0);
  });

  it("sorts merged leaderboard by overall score descending", async () => {
    const result = await loadAllResults(
      async () => fixtureRuns.runs, // overall 0.78
      async () => [
        {
          ...communityModel,
          model: "community-low",
          metrics: { ...communityModel.metrics, overall_score: 0.3 },
          source: "community",
        } as ModelSummary,
        {
          ...communityModel,
          model: "community-high",
          metrics: { ...communityModel.metrics, overall_score: 0.95 },
          source: "community",
        } as ModelSummary,
      ],
    );
    expect(result.leaderboard[0].model).toBe("community-high");
    expect(result.leaderboard[1].model).toBe("test-model");
    expect(result.leaderboard[2].model).toBe("community-low");
  });

  it("handles empty local results gracefully", async () => {
    const result = await loadAllResults(
      async () => [],
      async () => [],
    );
    expect(result.leaderboard.length).toBe(0);
    expect(result.localCount).toBe(0);
    expect(result.communityCount).toBe(0);
  });

  it("generates a generated_at timestamp", async () => {
    const result = await loadAllResults(
      async () => fixtureRuns.runs,
      async () => [],
    );
    expect(result.generated_at).toBeTruthy();
    expect(typeof result.generated_at).toBe("string");
  });
});

// ═══════════════════════════════════════════════════════════════
// Demo data generator (via loadResults fallback)
// ═══════════════════════════════════════════════════════════════

describe("demo data (loadResults fallback)", () => {
  afterEach(() => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
  });

  it("produces 3 demo models when fs read fails", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    expect(result.length).toBe(3);
  });

  it("produces demo models with expected names", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    const names = result.map((r) => r.model).sort();
    expect(names).toEqual([
      "gemma-4-e4b",
      "lfm2.5-8b-a1b",
      "qwopus3.5-9b-coder",
    ]);
  });

  it("gives each demo model a unique run_id prefixed with 'demo_'", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    expect(result.every((r) => r.run_id.startsWith("demo_"))).toBe(true);
    const ids = result.map((r) => r.run_id);
    expect(new Set(ids).size).toBe(3);
  });

  it("gives each demo model metadata (size, quantization)", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    for (const r of result) {
      expect(r.model_metadata.size).toBe("7B");
      expect(r.model_metadata.quantization).toBe("Q4_K_M");
    }
  });

  it("gives each demo model hardware info", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    for (const r of result) {
      expect(r.hardware.processor).toBe("Apple M3 Pro");
      expect(r.hardware.memory_gb).toBe(18);
    }
  });

  it("computes overall_score from weighted metrics", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    // qwopus3.5-9b-coder: 0.82*0.4 + 0.78*0.3 + 0.9*0.2 + 0.72*0.1 = 0.814
    const qwopus = result.find((r) => r.model === "qwopus3.5-9b-coder")!;
    expect(qwopus.metrics.overall_score).toBeCloseTo(0.814, 3);
    expect(qwopus.metrics.coding_score).toBe(0.82);
    expect(qwopus.metrics.reasoning_score).toBe(0.78);
    expect(qwopus.metrics.instruction_score).toBe(0.9);
  });

  it("assigns performance metrics with varying tokens_per_sec", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    const tpsValues = result.map((r) => r.performance.tokens_per_sec);
    expect(tpsValues).toContain(72);
    expect(tpsValues).toContain(65);
    expect(tpsValues).toContain(58);
  });

  it("assigns failure data with some non-zero values", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    for (const r of result) {
      const totalFailures = Object.values(r.failures).reduce(
        (a, b) => a + b,
        0,
      );
      expect(totalFailures).toBeGreaterThan(0);
    }
  });

  it("assigns each demo model 5 runs", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    for (const r of result) {
      expect(r.stats.runs).toBe(5);
    }
  });

  it("assigns a git_sha and git_branch to each demo model", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    for (const r of result) {
      expect(r.git_sha).toBe("abc1234");
      expect(r.git_branch).toBe("main");
    }
  });

  it("assigns packs_used and seed to each demo model", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const result = await loadResults();
    for (const r of result) {
      expect(r.packs_used).toEqual([
        "nestjs-pack",
        "react-pack",
        "debugging-pack",
      ]);
      expect(r.seed).toBe(42);
    }
  });

  it("falls back to demo data when results.json has no runs", async () => {
    mockReadFileSync.mockReturnValue(
      JSON.stringify({
        version: "1",
        generated_at: "",
        total_models: 0,
        total_runs: 0,
        runs: [],
      }),
    );
    const result = await loadResults();
    expect(result.length).toBe(3);
  });
});

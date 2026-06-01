/**
 * Data loading utilities for the dashboard.
 * Loads benchmark results from JSON files and provides typed access.
 */

// ── Types ─────────────────────────────────────────────────────────

export interface HardwareInfo {
  platform: string;
  processor: string;
  memory_gb: number;
  architecture: string;
}

export interface MetricScores extends Record<string, number> {
  coding_score: number;
  reasoning_score: number;
  instruction_score: number;
  frontend_score: number;
  math_score: number;
  debugging_score: number;
  overall_score: number;
}

export interface PerformanceMetrics {
  tokens_per_sec: number;
  normalized_tps: number;
  ttft_ms: number;
  total_latency_ms: number;
  memory_pressure_mb: number;
}

export interface RunStats {
  mean: number;
  std: number;
  min: number;
  max: number;
  median: number;
  runs: number;
  confidence_95: [number, number] | null;
  coefficient_of_variation: number;
}

export interface FailureBreakdown extends Record<string, number> {
  hallucinated_api: number;
  wrong_async_usage: number;
  incorrect_json_schema: number;
  syntax_error: number;
  logic_error: number;
  type_error: number;
  missing_import: number;
  stale_closure: number;
  race_condition: number;
  incorrect_di: number;
  oververbose: number;
  missed_constraint: number;
  other: number;
}

export interface BenchmarkResult {
  run_id: string;
  model: string;
  model_metadata: Record<string, string>;
  hardware: HardwareInfo;
  timestamp: string;
  git_sha: string;
  git_branch: string;
  metrics: MetricScores;
  performance: PerformanceMetrics;
  stats: RunStats;
  failures: FailureBreakdown;
  category_scores: Record<string, Record<string, number>>;
  config_snapshot: Record<string, unknown>;
  prompt_version: string;
  packs_used: string[];
  seed: number | null;
}

export interface AggregatedResults {
  version: string;
  generated_at: string;
  total_models: number;
  total_runs: number;
  runs: BenchmarkResult[];
}

export interface ModelSummary {
  model: string;
  metadata: Record<string, string>;
  best_run_id: string;
  metrics: MetricScores;
  performance: PerformanceMetrics;
  stats: { mean: number; std: number; runs: number };
  total_failures: number;
}

export interface LeaderboardData {
  leaderboard: ModelSummary[];
  generated_at: string;
}

// ── Loaders ────────────────────────────────────────────────────────

const RESULTS_URL = "/results.json";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Load all benchmark results from the aggregated results.json file.
 *
 * At build time (SSR / static generation): reads results.json directly from
 * the filesystem so static pages are pre-rendered with real data.
 *
 * At browser runtime (client:load hydration): fetches /results.json over HTTP.
 */
export async function loadResults(): Promise<BenchmarkResult[]> {
  if (import.meta.env.SSR) {
    // ── Build-time: read from filesystem ──────────────────────
    try {
      const fs = await import("fs");
      const path = await import("path");
      // Resolve relative to the Astro project root (CWD during build)
      const filePath = path.resolve(process.cwd(), "public", "results.json");
      const raw = fs.readFileSync(filePath, "utf-8");
      const data: AggregatedResults = JSON.parse(raw);
      if (data.runs && data.runs.length > 0) {
        return data.runs;
      }
      console.warn("results.json has no runs. Using demo data.");
    } catch (err) {
      console.warn(
        `No results.json found at build time (${(err as Error).message || err}). Using demo data.`
      );
    }
    return generateDemoData();
  }

  // ── Browser runtime: fetch over HTTP ────────────────────────
  try {
    const data = await fetchJson<AggregatedResults>(RESULTS_URL);
    if (data.runs && data.runs.length > 0) {
      return data.runs;
    }
    console.warn("results.json has no runs. Using demo data.");
  } catch {
    console.warn("No results.json found at runtime. Using demo data.");
  }
  return generateDemoData();
}

/**
 * Generate a leaderboard from loaded results.
 */
export function buildLeaderboard(results: BenchmarkResult[]): LeaderboardData {
  const byModel = new Map<string, BenchmarkResult[]>();

  for (const r of results) {
    if (!byModel.has(r.model)) {
      byModel.set(r.model, []);
    }
    byModel.get(r.model)!.push(r);
  }

  const models: ModelSummary[] = [];

  for (const [model, runs] of byModel) {
    const best = runs.reduce((a, b) =>
      a.metrics.overall_score > b.metrics.overall_score ? a : b,
    );

    models.push({
      model,
      metadata: best.model_metadata,
      best_run_id: best.run_id,
      metrics: best.metrics,
      performance: best.performance,
      stats: {
        mean: best.stats.mean,
        std: best.stats.std,
        runs: best.stats.runs,
      },
      total_failures: Object.values(best.failures).reduce((a, b) => a + b, 0),
    });
  }

  models.sort((a, b) => b.metrics.overall_score - a.metrics.overall_score);

  return {
    leaderboard: models,
    generated_at: new Date().toISOString(),
  };
}

/**
 * Aggregate failures across all results for the heatmap.
 */
export function aggregateFailures(results: BenchmarkResult[]): {
  labels: string[];
  counts: number[];
} {
  const totals: Record<string, number> = {};

  for (const r of results) {
    for (const [key, count] of Object.entries(r.failures)) {
      totals[key] = (totals[key] || 0) + count;
    }
  }

  const entries = Object.entries(totals)
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1]);

  // Friendly labels
  const labelMap: Record<string, string> = {
    hallucinated_api: "Hallucinated API",
    wrong_async_usage: "Wrong Async",
    incorrect_json_schema: "Bad JSON Schema",
    syntax_error: "Syntax Error",
    logic_error: "Logic Error",
    type_error: "Type Error",
    missing_import: "Missing Import",
    stale_closure: "Stale Closure",
    race_condition: "Race Condition",
    incorrect_di: "Bad DI",
    oververbose: "Oververbose",
    missed_constraint: "Missed Constraint",
    other: "Other",
  };

  return {
    labels: entries.map(([key]) => labelMap[key] || key),
    counts: entries.map(([, count]) => count),
  };
}

/**
 * Group results by model for per-model views.
 */
export function groupByModel(
  results: BenchmarkResult[],
): Map<string, BenchmarkResult[]> {
  const map = new Map<string, BenchmarkResult[]>();
  for (const r of results) {
    if (!map.has(r.model)) map.set(r.model, []);
    map.get(r.model)!.push(r);
  }
  return map;
}

// ── Demo Data ──────────────────────────────────────────────────────

function generateDemoData(): BenchmarkResult[] {
  const models = [
    {
      name: "qwopus3.5-9b-coder",
      coding: 0.82,
      reasoning: 0.78,
      instruction: 0.9,
      tps: 72,
      ttft: 420,
    },
    {
      name: "gemma-4-e4b",
      coding: 0.76,
      reasoning: 0.8,
      instruction: 0.94,
      tps: 65,
      ttft: 340,
    },
    {
      name: "lfm2.5-8b-a1b",
      coding: 0.8,
      reasoning: 0.85,
      instruction: 0.88,
      tps: 58,
      ttft: 510,
    },
  ];

  const failureTemplates: FailureBreakdown[] = [
    {
      hallucinated_api: 3,
      wrong_async_usage: 2,
      incorrect_json_schema: 1,
      syntax_error: 0,
      logic_error: 4,
      type_error: 2,
      missing_import: 1,
      stale_closure: 1,
      race_condition: 2,
      incorrect_di: 0,
      oververbose: 1,
      missed_constraint: 0,
      other: 0,
    },
    {
      hallucinated_api: 1,
      wrong_async_usage: 1,
      incorrect_json_schema: 0,
      syntax_error: 2,
      logic_error: 3,
      type_error: 3,
      missing_import: 2,
      stale_closure: 0,
      race_condition: 1,
      incorrect_di: 0,
      oververbose: 2,
      missed_constraint: 1,
      other: 0,
    },
    {
      hallucinated_api: 0,
      wrong_async_usage: 1,
      incorrect_json_schema: 0,
      syntax_error: 0,
      logic_error: 2,
      type_error: 1,
      missing_import: 0,
      stale_closure: 0,
      race_condition: 0,
      incorrect_di: 1,
      oververbose: 0,
      missed_constraint: 0,
      other: 1,
    },
  ];

  return models.map((m, i) => ({
    run_id: `demo_${m.name}`,
    model: m.name,
    model_metadata: { size: "7B", quantization: "Q4_K_M" },
    hardware: {
      platform: "macOS 14.5",
      processor: "Apple M3",
      memory_gb: 18,
      architecture: "arm64",
    },
    timestamp: new Date().toISOString(),
    git_sha: "abc1234",
    git_branch: "main",
    metrics: {
      coding_score: m.coding,
      reasoning_score: m.reasoning,
      instruction_score: m.instruction,
      frontend_score: 0.72,
      math_score: 0.75,
      debugging_score: 0.68,
      overall_score:
        m.coding * 0.4 + m.reasoning * 0.3 + m.instruction * 0.2 + 0.72 * 0.1,
    },
    performance: {
      tokens_per_sec: m.tps,
      normalized_tps: m.tps * 0.95,
      ttft_ms: m.ttft,
      total_latency_ms: m.ttft + 2500,
      memory_pressure_mb: 1200 + i * 400,
    },
    stats: {
      mean: 0.81 - i * 0.03,
      std: 0.05 + i * 0.01,
      min: 0.75 - i * 0.05,
      max: 0.88 - i * 0.01,
      median: 0.82 - i * 0.03,
      runs: 5,
      confidence_95: [0.78 - i * 0.03, 0.85 - i * 0.02],
      coefficient_of_variation: 0.06 + i * 0.01,
    },
    failures: failureTemplates[i],
    category_scores: {},
    config_snapshot: { temperature: 0.2, max_tokens: 1000 },
    prompt_version: "v1",
    packs_used: ["nestjs-pack", "react-pack", "debugging-pack"],
    seed: 42,
  }));
}

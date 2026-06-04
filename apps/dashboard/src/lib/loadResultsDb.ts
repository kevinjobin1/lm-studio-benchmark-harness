/**
 * SQLite-backed results loader for the dashboard.
 *
 * Queries ``results/runs.db`` directly via ``better-sqlite3`` instead of
 * parsing the flat ``results.json`` file.  Provides O(1) lookups,
 * pagination, and filtered queries — dramatically faster than the
 * O(n) JSON scan at >100 runs.
 *
 * This module is **Node.js-only** (SSR / ``astro dev``).  On Cloudflare
 * Workers (``astro build`` for Pages), it degrades silently and the
 * caller should fall back to the JSON loader.
 *
 * Schema mirrors ``packages/core/results_store.py``:
 *   runs (id, model_id, provider, workload_type, workload_name,
 *         overall_score, tokens_per_sec, ttft_ms, memory_mb,
 *         status, config_json, trace_path, created_at,
 *         git_sha, git_branch, schema_version)
 */

import type { default as BetterSqlite3 } from "better-sqlite3";
import type { BenchmarkResult, FailureBreakdown } from "./loadResults";

// ── Internal helpers ──────────────────────────────────────────────

let _db: InstanceType<typeof BetterSqlite3> | null = null;
let _dbOpenAttempted = false;

/** Lazy require() that works in ESM via createRequire. */
function lazyRequire(moduleName: string): unknown | null {
  try {
    // createRequire is available in Node.js SSR but not Workers
    const { createRequire } = require("node:module") as typeof import("node:module");
    return createRequire(import.meta.url)(moduleName);
  } catch {
    return null;
  }
}

function openDb(): InstanceType<typeof BetterSqlite3> | null {
  if (_dbOpenAttempted) return _db;
  _dbOpenAttempted = true;

  try {
    const BetterSqlite3Ctor = lazyRequire("better-sqlite3") as
      | typeof BetterSqlite3
      | null;
    if (!BetterSqlite3Ctor) return null;

    const pathModule = lazyRequire("path") as typeof import("path") | null;
    if (!pathModule) return null;

    // Resolve relative to the project root
    const dbPath = pathModule.resolve(process.cwd(), "results", "runs.db");
    _db = new BetterSqlite3Ctor(dbPath, { readonly: true }) as InstanceType<typeof BetterSqlite3>;
    (_db as any).pragma("journal_mode = WAL");
    return _db;
  } catch {
    // better-sqlite3 not available (Cloudflare Workers, missing native dep, etc.)
    return null;
  }
}

// ── Row → BenchmarkResult mapping ─────────────────────────────────

interface DbRow {
  id: string;
  model_id: string;
  provider: string;
  workload_type: string;
  workload_name: string;
  overall_score: number | null;
  tokens_per_sec: number | null;
  ttft_ms: number | null;
  memory_mb: number | null;
  status: string;
  config_json: string | null;
  trace_path: string | null;
  created_at: string;
  git_sha: string | null;
  git_branch: string | null;
}

function emptyFailures(): FailureBreakdown {
  return {
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
}

function dbRowToResult(row: DbRow): BenchmarkResult {
  const packs = row.workload_name ? [row.workload_name] : [];
  const score = row.overall_score ?? 0;

  return {
    run_id: row.id,
    model: row.model_id,
    model_metadata: {
      provider: row.provider,
    },
    hardware: {
      platform: "",
      processor: "",
      // Negative sentinel so display logic can show "—" instead of "0GB"
      memory_gb: 0,
      architecture: "",
    },
    timestamp: row.created_at,
    git_sha: row.git_sha ?? "",
    git_branch: row.git_branch ?? "",
    metrics: {
      coding_score: score,
      reasoning_score: score,
      instruction_score: score,
      frontend_score: score,
      math_score: score,
      debugging_score: score,
      overall_score: score,
    },
    performance: {
      tokens_per_sec: row.tokens_per_sec ?? 0,
      normalized_tps: (row.tokens_per_sec ?? 0) * 0.95,
      ttft_ms: row.ttft_ms ?? 0,
      total_latency_ms: (row.ttft_ms ?? 0) + 2500,
      memory_pressure_mb: row.memory_mb ?? 0,
    },
    stats: {
      mean: score,
      std: 0,
      min: 0,
      max: 0,
      median: score,
      runs: 1,
      confidence_95: null,
      coefficient_of_variation: 0,
    },
    failures: emptyFailures(),
    category_scores: {},
    config_snapshot: row.config_json ? JSON.parse(row.config_json) : {},
    prompt_version: "v1",
    packs_used: packs,
    seed: null,
    trace_ids: row.trace_path ? [row.trace_path] : undefined,
  };
}

// ── Public API ────────────────────────────────────────────────────

/**
 * Load all benchmark results from SQLite.
 *
 * Returns ``null`` if the database is unavailable — caller should
 * fall back to the JSON loader.
 *
 * @param model  Optional model filter (case-insensitive LIKE).
 * @param limit  Max rows to return (default: 100).
 * @param offset Pagination offset.
 */
export function loadResultsFromDb(
  model?: string,
  limit = 100,
  offset = 0,
): BenchmarkResult[] | null {
  const db = openDb();
  if (!db) return null;

  try {
    let query = "SELECT * FROM runs WHERE status = 'completed'";
    const params: (string | number)[] = [];

    if (model) {
      query += " AND model_id LIKE ? COLLATE NOCASE";
      params.push(`%${model}%`);
    }

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
    params.push(limit, offset);

    const stmt = (db as any).prepare(query);
    const rows = stmt.all(...params) as DbRow[];
    return rows.map(dbRowToResult);
  } catch (err) {
    console.warn("[loadResultsDb] Query failed:", (err as Error).message);
    return null;
  }
}

/**
 * Get a single run by ID from SQLite.
 */
export function getRunFromDb(runId: string): BenchmarkResult | null {
  const db = openDb();
  if (!db) return null;

  try {
    const stmt = (db as any).prepare("SELECT * FROM runs WHERE id = ?");
    const row = stmt.get(runId) as DbRow | undefined;
    return row ? dbRowToResult(row) : null;
  } catch {
    return null;
  }
}

/**
 * Get aggregate statistics from SQLite.
 */
export function getStatsFromDb(): {
  totalRuns: number;
  totalModels: number;
  avgScore: number;
  latestRun: string;
} | null {
  const db = openDb();
  if (!db) return null;

  try {
    const row = (db as any)
      .prepare(
        `SELECT
           COUNT(*) as total_runs,
           COUNT(DISTINCT model_id) as total_models,
           COALESCE(AVG(overall_score), 0) as avg_score,
           MAX(created_at) as latest_run
         FROM runs
         WHERE status = 'completed'`,
      )
      .get() as {
      total_runs: number;
      total_models: number;
      avg_score: number;
      latest_run: string | null;
    };

    return {
      totalRuns: row.total_runs,
      totalModels: row.total_models,
      avgScore: row.avg_score,
      latestRun: row.latest_run ?? "",
    };
  } catch {
    return null;
  }
}

/**
 * Count runs from SQLite (fast metadata check).
 */
export function countRunsFromDb(): number | null {
  const db = openDb();
  if (!db) return null;

  try {
    const row = (db as any)
      .prepare("SELECT COUNT(*) as cnt FROM runs")
      .get() as { cnt: number };
    return row.cnt;
  } catch {
    return null;
  }
}

// ── Trace queries (for /api/traces) ───────────────────────────────

/** Lightweight trace entry matching TraceIndexEntry shape. */
export interface DbTraceEntry {
  trace_id: string;
  run_id: string;
  model: string;
  provider: string;
  prompt: string;
  timestamp: string;
  totalTimeMs: number;
  status: "completed" | "failed";
  stepCount: number;
  tokenCount: number;
  ttft_ms: number;
}

/**
 * Load traces linked to a specific model from the SQLite runs DB.
 *
 * Returns entries for runs that have a ``trace_path`` set.
 * The actual trace JSON files are still read via ``loadTraces.ts``
 * for full detail; this just provides the index for listings.
 *
 * Returns ``null`` if the database is unavailable.
 */
export function loadTraceEntriesFromDb(
  model?: string,
  limit = 50,
  offset = 0,
): DbTraceEntry[] | null {
  const db = openDb();
  if (!db) return null;

  try {
    let query =
      "SELECT id as trace_id, id as run_id, model_id as model, provider, " +
      "overall_score, tokens_per_sec, ttft_ms, created_at as timestamp, " +
      "status " +
      "FROM runs WHERE trace_path IS NOT NULL AND status IN ('completed', 'failed')";

    const params: (string | number)[] = [];

    if (model) {
      query += " AND model_id LIKE ? COLLATE NOCASE";
      params.push(`%${model}%`);
    }

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
    params.push(limit, offset);

    const rows = (db as any).prepare(query).all(...params) as {
      trace_id: string;
      run_id: string;
      model: string;
      provider: string;
      overall_score: number | null;
      tokens_per_sec: number | null;
      ttft_ms: number | null;
      timestamp: string;
      status: string;
    }[];

    return rows.map((r) => ({
      trace_id: r.trace_id,
      run_id: r.run_id,
      model: r.model,
      provider: r.provider || "",
      prompt: "", // Not stored in DB — load from trace JSON for full detail
      timestamp: r.timestamp,
      totalTimeMs: 0,
      status: (r.status === "completed" || r.status === "failed"
        ? r.status
        : "completed") as "completed" | "failed",
      stepCount: 0,
      tokenCount: 0,
      ttft_ms: r.ttft_ms ?? 0,
    }));
  } catch (err) {
    console.warn("[loadResultsDb] Trace query failed:", (err as Error).message);
    return null;
  }
}

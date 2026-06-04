/**
 * SQLite metrics loader for the dashboard.
 *
 * Reads from the ``results/metrics.db`` SQLite database (created by
 * ``MetricsStore`` in the Python CLI) and provides typed query functions
 * for the dashboard API routes.
 */

// ── Types ──────────────────────────────────────────────────────────

export interface MetricPoint {
  id: number;
  name: string;
  value: number;
  unit: string;
  tags_json: string;
  model: string;
  run_id: string;
  source: string;
  timestamp_ms: number;
  created_at: string;
}

export interface MetricStats {
  metric: string;
  count: number;
  avg: number | null;
  min: number | null;
  max: number | null;
  sum: number | null;
  p50: number | null;
  p95: number | null;
  p99: number | null;
  model_count: number;
  run_count: number;
}

export interface TimeBucket {
  bucket: string;
  count: number;
  avg: number | null;
  min: number | null;
  max: number | null;
}

export interface MetricsQuery {
  metric?: string;
  model?: string;
  runId?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
  order?: "ASC" | "DESC";
  bucket?: number;
  stats?: boolean;
  count?: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────

/** Resolve project root (works when cwd is project root or apps/dashboard). */
function resolveProjectRoot(): string {
  const cwd = process.cwd();
  if (cwd.endsWith("apps/dashboard")) {
    return cwd.replace(/\/apps\/dashboard$/, "");
  }
  if (cwd.endsWith("apps")) {
    return cwd.replace(/\/apps$/, "");
  }
  return cwd;
}

/** Resolve the path to metrics.db. */
function metricsDbPath(): string {
  const root = resolveProjectRoot();
  return `${root}/results/metrics.db`;
}

// ── Database connection ────────────────────────────────────────────

let _db: import("better-sqlite3").Database | null = null;

function getDb(): import("better-sqlite3").Database | null {
  if (_db) return _db;
  try {
    const Database = require("better-sqlite3");
    const path = metricsDbPath();
    _db = new Database(path, { readonly: true });
    _db!.pragma("journal_mode=WAL");
    return _db;
  } catch {
    // better-sqlite3 not available (e.g. Cloudflare Workers)
    return null;
  }
}

// ── Query functions ────────────────────────────────────────────────

/**
 * Load raw metric data points from SQLite.
 */
export function loadMetricsFromDb(
  query: MetricsQuery,
): MetricPoint[] | MetricStats | TimeBucket[] | Record<string, number> | number {
  const db = getDb();
  if (!db) return [];

  const conditions: string[] = [];
  const params: any[] = [];

  if (query.metric) {
    conditions.push("name = ?");
    params.push(query.metric);
  }
  if (query.model) {
    conditions.push("model LIKE ? COLLATE NOCASE");
    params.push(`%${query.model}%`);
  }
  if (query.runId) {
    conditions.push("run_id = ?");
    params.push(query.runId);
  }
  if (query.since) {
    conditions.push("created_at >= ?");
    params.push(query.since);
  }
  if (query.until) {
    conditions.push("created_at <= ?");
    params.push(query.until);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  // ── Count mode ────────────────────────────────────────────
  if (query.count) {
    const row = db.prepare(`SELECT COUNT(*) as cnt FROM metrics ${where}`).get(...params) as
      | { cnt: number }
      | undefined;
    return row?.cnt ?? 0;
  }

  // ── Stats mode ────────────────────────────────────────────
  if (query.stats && query.metric) {
    const agg = db.prepare(`
      SELECT
        COUNT(*) as count,
        AVG(value) as avg,
        MIN(value) as min,
        MAX(value) as max,
        SUM(value) as sum
      FROM metrics ${where}
    `).get(...params) as {
      count: number;
      avg: number | null;
      min: number | null;
      max: number | null;
      sum: number | null;
    };

    // Percentiles in JS
    const values = db
      .prepare(`SELECT value FROM metrics ${where} ORDER BY value ASC`)
      .all(...params)
      .map((r: any) => r.value as number);

    function percentile(sorted: number[], p: number): number {
      if (sorted.length === 0) return 0;
      const k = (p / 100) * (sorted.length - 1);
      const f = Math.floor(k);
      const c = k - f;
      if (f + 1 < sorted.length) {
        return Number((sorted[f] * (1 - c) + sorted[f + 1] * c).toFixed(4));
      }
      return sorted[sorted.length - 1];
    }

    // Count distinct models and run_ids
    const meta = db.prepare(`
      SELECT
        COUNT(DISTINCT model) as model_count,
        COUNT(DISTINCT run_id) as run_count
      FROM metrics ${where}
    `).get(...params) as { model_count: number; run_count: number };

    return {
      metric: query.metric,
      count: agg.count,
      avg: agg.avg !== null ? Number(agg.avg.toFixed(4)) : null,
      min: agg.min !== null ? Number(agg.min.toFixed(4)) : null,
      max: agg.max !== null ? Number(agg.max.toFixed(4)) : null,
      sum: agg.sum !== null ? Number(agg.sum.toFixed(4)) : null,
      p50: percentile(values, 50),
      p95: percentile(values, 95),
      p99: percentile(values, 99),
      model_count: meta.model_count,
      run_count: meta.run_count,
    } as MetricStats;
  }

  // ── Bucket mode ───────────────────────────────────────────
  if (query.bucket && query.metric) {
    const bucketMs = query.bucket * 1000;
    const buckets = db
      .prepare(`
        SELECT
          (CAST(timestamp_ms AS INTEGER) / ${bucketMs}) * ${bucketMs} AS bucket_epoch,
          COUNT(*) as count,
          AVG(value) as avg,
          MIN(value) as min,
          MAX(value) as max
        FROM metrics ${where}
        GROUP BY bucket_epoch
        ORDER BY bucket_epoch ASC
      `)
      .all(...params) as { bucket_epoch: number; count: number; avg: number | null; min: number | null; max: number | null }[];

    return buckets.map((b) => ({
      bucket: new Date(b.bucket_epoch).toISOString(),
      count: b.count,
      avg: b.avg !== null ? Number(b.avg.toFixed(4)) : null,
      min: b.min !== null ? Number(b.min.toFixed(4)) : null,
      max: b.max !== null ? Number(b.max.toFixed(4)) : null,
    })) as TimeBucket[];
  }

  // ── Latest mode ───────────────────────────────────────────
  if (query.metric === undefined) {
    // Return latest value for each metric
    const extraWhere = query.model ? `WHERE model LIKE ? COLLATE NOCASE` : "";
    const extraParams = query.model ? [`%${query.model}%`] : [];
    const rows = db
      .prepare(`
        SELECT name, value FROM metrics
        WHERE id IN (
          SELECT MAX(id) FROM metrics ${extraWhere} GROUP BY name
        )
      `)
      .all(...extraParams) as { name: string; value: number }[];

    const result: Record<string, number> = {};
    for (const row of rows) {
      result[row.name] = row.value;
    }
    return result;
  }

  // ── Raw time-series mode ──────────────────────────────────
  const orderClause = query.order === "ASC" ? "ASC" : "DESC";
  const lim = query.limit ?? 100;
  const off = query.offset ?? 0;

  const rows = db
    .prepare(
      `SELECT * FROM metrics ${where} ORDER BY created_at ${orderClause}, id ${orderClause} LIMIT ? OFFSET ?`,
    )
    .all(...params, lim, off) as MetricPoint[];

  return rows;
}

/**
 * Load distinct metric names and model names from the metrics store.
 */
export function loadMetricsList(): {
  metrics: string[];
  models: string[];
} {
  const db = getDb();
  if (!db) return { metrics: [], models: [] };

  const metrics = db
    .prepare("SELECT DISTINCT name FROM metrics ORDER BY name")
    .all()
    .map((r: any) => r.name as string);

  const models = db
    .prepare(
      "SELECT DISTINCT model FROM metrics WHERE model != '' ORDER BY model",
    )
    .all()
    .map((r: any) => r.model as string);

  return { metrics, models };
}

import type { APIRoute } from "astro";
import { loadMetricsFromDb } from "../../lib/loadMetricsDb";

/**
 * GET /api/metrics
 *
 * Returns time-series metrics data from the SQLite metrics store.
 *
 * Query params:
 *   metric   — metric name (e.g. "tokens_per_second", "ttft_ms", required)
 *   model    — filter by model name (case-insensitive partial match)
 *   run_id   — filter by specific run
 *   since    — ISO 8601 start time
 *   until    — ISO 8601 end time
 *   limit    — max data points (default: 100)
 *   offset   — pagination offset (default: 0)
 *   order    — "ASC" (chronological) or "DESC" (default: DESC)
 *   bucket   — time bucket in seconds (e.g. 3600 for hourly agg)
 *   stats    — if "true", return aggregate stats instead of raw series
 *   latest   — if "true", return latest value for each metric
 *
 * Response:
 *   - Raw series: { metric, values: [{ value, timestamp_ms, created_at, model, run_id }], total }
 *   - Stats:      { metric, avg, min, max, count, p50, p95, p99, model_count, run_count }
 *   - Latest:     { metrics: { "tokens_per_second": 72.3, ... } }
 *   - Bucketed:   [{ bucket: "2026-01-01T00:00:00", avg, min, max, count }]
 */
export const GET: APIRoute = async ({ request }) => {
  const url = new URL(request.url);
  const metric = url.searchParams.get("metric") || undefined;
  const model = url.searchParams.get("model") || undefined;
  const runId = url.searchParams.get("run_id") || undefined;
  const since = url.searchParams.get("since") || undefined;
  const until = url.searchParams.get("until") || undefined;
  const limit = url.searchParams.has("limit")
    ? parseInt(url.searchParams.get("limit")!, 10)
    : 100;
  const offset = url.searchParams.has("offset")
    ? parseInt(url.searchParams.get("offset")!, 10)
    : 0;
  const order = (url.searchParams.get("order") || "DESC").toUpperCase() === "ASC"
    ? "ASC"
    : "DESC";
  const bucket = url.searchParams.has("bucket")
    ? parseInt(url.searchParams.get("bucket")!, 10)
    : undefined;
  const doStats = url.searchParams.get("stats") === "true";
  const doLatest = url.searchParams.get("latest") === "true";

  const doList = url.searchParams.get("action") === "list";

  // Handle list mode (distinct metric names and models)
  if (doList) {
    if (!import.meta.env.SSR) {
      return new Response(JSON.stringify({ metrics: [], models: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    try {
      const { loadMetricsList } = await import("../../lib/loadMetricsDb");
      const result = loadMetricsList();
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    } catch {
      return new Response(JSON.stringify({ metrics: [], models: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
  }

  // Validate required metric name for non-latest queries
  if (!metric && !doLatest) {
    return new Response(
      JSON.stringify({ error: "Missing required query param: metric" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // Try SQLite metrics store (SSR mode only)
  if (import.meta.env.SSR) {
    try {
      if (doLatest) {
        const latest = loadMetricsFromDb({ metric, model });
        return new Response(JSON.stringify({ metrics: latest }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (bucket) {
        const bucketed = loadMetricsFromDb({
          metric: metric!,
          model,
          since,
          until,
          bucket,
        });
        return new Response(JSON.stringify({ metric, buckets: bucketed }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (doStats) {
        const stats = loadMetricsFromDb({
          metric: metric!,
          model,
          runId,
          since,
          until,
          stats: true,
        });
        return new Response(JSON.stringify(stats), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      // Raw time-series query
      const values = loadMetricsFromDb({
        metric: metric!,
        model,
        runId,
        since,
        until,
        limit,
        offset,
        order,
      });
      const total = loadMetricsFromDb({
        metric: metric!,
        model,
        runId,
        since,
        until,
        count: true,
      });

      return new Response(
        JSON.stringify({
          metric,
          model: model || null,
          values,
          total,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    } catch (err) {
      // Metrics DB not available — return descriptive empty response
      return new Response(
        JSON.stringify({
          metric,
          model: model || null,
          values: [],
          total: 0,
          error: err instanceof Error ? err.message : "Metrics store unavailable",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
  }

  // Browser runtime — metrics are SSR-only, return empty
  return new Response(
    JSON.stringify({
      metric: metric || null,
      values: [],
      total: 0,
      note: "Metrics API is available during SSR only (local dev / build time)",
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
};



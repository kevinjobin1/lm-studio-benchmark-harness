import type { APIRoute } from "astro";

/**
 * GET /api/regression
 *
 * Returns regression alerts from the AlertStore SQLite database.
 *
 * Query params:
 *   model    — filter by model name (optional)
 *   metric   — filter by metric name (optional)
 *   severity — filter by severity: "critical" | "warning" | "info" (optional)
 *   limit    — max entries to return (default: 50)
 *   offset   — pagination offset (default: 0)
 *
 * Response:
 * {
 *   stats: { total, critical, warning, info, models, metrics },
 *   alerts: RegressionAlert[]
 * }
 */
export const GET: APIRoute = async ({ request }) => {
  const url = new URL(request.url);
  const model = url.searchParams.get("model") || undefined;
  const metric = url.searchParams.get("metric") || undefined;
  const severityParam: "critical" | "warning" | "info" | undefined =
    (url.searchParams.get("severity") as "critical" | "warning" | "info" | null) || undefined;
  const limitParam = url.searchParams.get("limit");
  const offsetParam = url.searchParams.get("offset");

  const limit = limitParam ? parseInt(limitParam, 10) : 50;
  const offset = offsetParam ? parseInt(offsetParam, 10) : 0;

  // SSR-only: query SQLite AlertStore directly
  if (import.meta.env.SSR) {
    try {
      const { execSync } = await import("child_process");

      // Query the alert store via a Python helper script
      const args = [model ? `--model ${model}` : "", metric ? `--metric ${metric}` : ""]
        .filter(Boolean)
        .join(" ");
      const severityFlag = severityParam ? `--severity ${severityParam}` : "";
      const cmd = [
        `python3 -c "`,
        `import sys; sys.path.insert(0, 'packages');`,
        `from core.regression import AlertStore;`,
        `import json;`,
        `store = AlertStore('results/metrics.db');`,
        `alerts = store.list_alerts(model=${JSON.stringify(model || "")} or None,`,
        `  metric=${JSON.stringify(metric || "")} or None,`,
        `  severity=${JSON.stringify(severityParam || "")} or None,`,
        `  limit=${limit}, offset=${offset});`,
        `stats = store.stats();`,
        `print(json.dumps({'stats': {k: v for k, v in stats.items()}, 'alerts': [a.to_dict() for a in alerts]}));`,
        `"`,
      ].join("");

      const result = execSync(cmd, {
        cwd: process.cwd(),
        encoding: "utf-8",
        timeout: 10000,
        maxBuffer: 1024 * 1024,
      });

      return new Response(result, {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    } catch {
      // Python or SQLite not available — return empty response
      return new Response(
        JSON.stringify({
          stats: { total: 0, critical: 0, warning: 0, info: 0, model_count: 0, metric_count: 0, latest_alert: null },
          alerts: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }
  }

  // Fallback for non-SSR (Cloudflare Workers, etc.)
  return new Response(
    JSON.stringify({
      stats: { total: 0, critical: 0, warning: 0, info: 0, model_count: 0, metric_count: 0, latest_alert: null },
      alerts: [],
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

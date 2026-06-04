import type { APIRoute } from "astro";

/**
 * GET /api/traces/diff
 *
 * Computes a structured three-level diff between two execution traces
 * using the Python ``trace_diff.py`` engine.
 *
 * Query params:
 *   trace_id_a  — ID of the first trace (required)
 *   trace_id_b  — ID of the second trace (required)
 *
 * Response: TraceDiffResult (summary, steps, metrics, artifacts)
 */
export const GET: APIRoute = async ({ request }) => {
  const url = new URL(request.url);
  const traceIdA = url.searchParams.get("trace_id_a");
  const traceIdB = url.searchParams.get("trace_id_b");

  if (!traceIdA || !traceIdB) {
    return new Response(
      JSON.stringify({ error: "Missing required query params: trace_id_a, trace_id_b" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // Try Python trace diff engine (SSR mode)
  // Security: trace IDs are passed as command-line arguments, not interpolated
  // into Python code, to prevent injection.
  if (import.meta.env.SSR) {
    try {
      const projectRoot = resolveProjectRoot();
      const { spawnSync } = await import("node:child_process");
      const traceDir = `${projectRoot}/results/traces`;

      // Validate trace IDs contain only safe characters
      const safeIdPattern = /^[a-zA-Z0-9_\-]+$/;
      if (!safeIdPattern.test(traceIdA) || !safeIdPattern.test(traceIdB)) {
        return new Response(
          JSON.stringify({ error: "Invalid trace ID format — use alphanumeric, hyphens, underscores only" }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        );
      }

      const pythonScript = [
        "import sys, json, os",
        `sys.path.insert(0, sys.argv[1])`,
        `sys.path.insert(0, sys.argv[2])`,
        "from core.trace_diff import diff_trace_files",
        "path_a = os.path.join(sys.argv[3], sys.argv[4] + '.json')",
        "path_b = os.path.join(sys.argv[3], sys.argv[5] + '.json')",
        "try:",
        "    result = diff_trace_files(path_a, path_b)",
        "    print(json.dumps(result))",
        "except FileNotFoundError as e:",
        "    print(json.dumps({'error': f'Trace file not found: {e}'}))",
        "except Exception as e:",
        "    print(json.dumps({'error': str(e)}))",
      ].join("\n");

      const result = spawnSync("python3", [
        "-c", pythonScript,
        projectRoot + "/packages",  // sys.argv[1]
        projectRoot,                // sys.argv[2]
        traceDir,                   // sys.argv[3]
        traceIdA,                   // sys.argv[4]
        traceIdB,                   // sys.argv[5]
      ], {
        cwd: projectRoot,
        timeout: 10000,
        encoding: "utf-8",
      });

      if (result.status === 0 && result.stdout) {
        const parsed = JSON.parse(result.stdout);
        if (parsed.error) {
          return new Response(JSON.stringify(parsed), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(result.stdout, {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      // Fall through to fallback
    } catch {
      // Python or traces unavailable — fall through
    }
  }

  // Fallback: return basic error — client falls back to simple client-side diff
  return new Response(
    JSON.stringify({
      error: "Trace diff engine unavailable. Run benchmarks to generate trace data.",
      trace_id_a: traceIdA,
      trace_id_b: traceIdB,
    }),
    { status: 404, headers: { "Content-Type": "application/json" } },
  );
};

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

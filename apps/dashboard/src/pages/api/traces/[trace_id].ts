import type { APIRoute } from "astro";
import { loadTrace } from "../../../lib/loadTraces";

/**
 * GET /api/traces/[trace_id]
 *
 * Returns a single trace by its trace_id.
 *
 * Response: TraceData | { error: string } (404 if not found)
 */
export const GET: APIRoute = async ({ params }) => {
  const { trace_id } = params;

  if (!trace_id) {
    return new Response(
      JSON.stringify({ error: "Missing trace_id" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const trace = await loadTrace(decodeURIComponent(trace_id));

  if (!trace) {
    return new Response(
      JSON.stringify({ error: `Trace not found: ${trace_id}` }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(JSON.stringify(trace), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

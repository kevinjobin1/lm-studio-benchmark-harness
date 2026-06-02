/**
 * Trace data loading utilities for the dashboard (V2).
 *
 * Provides typed access to captured execution traces stored in
 * public/traces/ as individual JSON files, plus a manifest index
 * at public/traces/index.json.
 */

import type { TraceRun } from "./traceTypes";

// ── Types (mirror Python trace_schema.py) ────────────────────────

export interface TraceStep {
  id: string;
  type: "system" | "prompt" | "token" | "tool_call" | "reasoning" | "response" | "error";
  label: string;
  detail?: string;
  timing_ms: number;
  tool?: string;
  input?: string;
  output?: string;
  status: "success" | "failure" | "pending";
}

export interface TraceMetrics {
  ttft_ms: number;
  tokens_per_second: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_latency_ms: number;
  memory_pressure_mb: number;
  token_timings_ms: number[];
}

export interface TraceArtifacts {
  response: string;
  logs: string[];
  errors: string[];
}

export interface TraceData {
  trace_id: string;
  run_id: string;
  model: string;
  provider: string;
  prompt: string;
  system_prompt?: string | null;
  pack: string;
  timestamp: string;
  totalTimeMs: number;
  status: "completed" | "failed" | "running";
  steps: TraceStep[];
  metrics: TraceMetrics;
  artifacts: TraceArtifacts;
  hardware?: Record<string, unknown> | null;
}

/** Lightweight entry in the trace index manifest. */
export interface TraceIndexEntry {
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

export interface TraceManifest {
  version: string;
  generated_at: string;
  total_traces: number;
  traces: TraceIndexEntry[];
}

/** Filters for listing traces. */
export interface TraceListOptions {
  model?: string;
  limit?: number;
  offset?: number;
  status?: "completed" | "failed";
}

/** Aggregated trace statistics for dashboard overview (V2). */
export interface TraceStats {
  total: number;
  modelsWithTraces: number;
  completed: number;
  failed: number;
}

// ── Helpers ────────────────────────────────────────────────────────

/** Convert a TraceData payload into a TraceRun for the Timeline UI. */
export function mapTraceToRun(t: TraceData): TraceRun {
  return {
    id: t.trace_id,
    model: t.model,
    pack: t.pack || "default",
    prompt: t.prompt?.slice(0, 100) || "(no prompt)",
    timestamp: t.timestamp
      ? new Date(t.timestamp).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        })
      : "",
    totalTimeMs: t.totalTimeMs,
    status: (t.status === "completed" || t.status === "failed"
      ? t.status
      : "completed") as TraceRun["status"],
    steps: (t.steps || []).map(s => ({
      id: s.id,
      type: s.type as TraceRun["steps"][0]["type"],
      label: s.label,
      detail: s.detail,
      timing_ms: s.timing_ms,
      tool: s.tool,
      input: s.input,
      output: s.output,
      status: s.status,
    })),
  };
}

// ── Loaders ────────────────────────────────────────────────────────

const TRACES_INDEX_URL = "/traces/index.json";

/**
 * Load the trace manifest (index of all available traces).
 */
export async function loadTraceManifest(): Promise<TraceManifest> {
  if (import.meta.env.SSR) {
    try {
      const fs = await import("fs");
      const path = await import("path");
      // Try public/traces/ first (where generate_traces_index.py outputs).
      // Fall back to results/traces/ (where benchmark saves raw trace files).
      const publicPath = path.resolve(
        process.cwd(),
        "public",
        "traces",
        "index.json",
      );
      const resultsPath = path.resolve(
        process.cwd(),
        "results",
        "traces",
        "index.json",
      );
      try {
        const raw = fs.readFileSync(publicPath, "utf-8");
        return JSON.parse(raw) as TraceManifest;
      } catch {
        const raw = fs.readFileSync(resultsPath, "utf-8");
        return JSON.parse(raw) as TraceManifest;
      }
    } catch {
      return emptyManifest();
    }
  }

  try {
    const resp = await fetch(TRACES_INDEX_URL);
    if (!resp.ok) return emptyManifest();
    return (await resp.json()) as TraceManifest;
  } catch {
    return emptyManifest();
  }
}

/**
 * Load a single trace by ID.
 * SSR: reads from results/traces/{trace_id}.json (where the benchmark saves).
 * Browser: fetches /api/traces/{trace_id}.
 */
export async function loadTrace(
  traceId: string,
): Promise<TraceData | null> {
  if (import.meta.env.SSR) {
    try {
      const fs = await import("fs");
      const path = await import("path");
      const filePath = path.resolve(
        process.cwd(),
        "results",
        "traces",
        `${traceId}.json`,
      );
      const raw = fs.readFileSync(filePath, "utf-8");
      return JSON.parse(raw) as TraceData;
    } catch {
      return null;
    }
  }

  try {
    const resp = await fetch(`/api/traces/${encodeURIComponent(traceId)}`);
    if (!resp.ok) return null;
    return (await resp.json()) as TraceData;
  } catch {
    return null;
  }
}

/**
 * Load a filtered list of traces.
 * SSR: reads manifest + filters.
 * Browser: fetches /api/traces with query params.
 */
export async function loadTraceList(
  options?: TraceListOptions,
): Promise<TraceIndexEntry[]> {
  if (import.meta.env.SSR) {
    const manifest = await loadTraceManifest();
    return filterManifest(manifest.traces, options);
  }

  const params = new URLSearchParams();
  if (options?.model) params.set("model", options.model);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.offset) params.set("offset", String(options.offset));
  if (options?.status) params.set("status", options.status);

  const query = params.toString();
  const url = `/api/traces${query ? `?${query}` : ""}`;
  try {
    const resp = await fetch(url);
    if (!resp.ok) return [];
    return (await resp.json()) as TraceIndexEntry[];
  } catch {
    return [];
  }
}

// ── Helpers ────────────────────────────────────────────────────────

function emptyManifest(): TraceManifest {
  return {
    version: "1.0.0",
    generated_at: new Date().toISOString(),
    total_traces: 0,
    traces: [],
  };
}

export function filterManifest(
  traces: TraceIndexEntry[],
  options?: TraceListOptions,
): TraceIndexEntry[] {
  let filtered = [...traces];

  if (options?.model) {
    const model = options.model.toLowerCase();
    filtered = filtered.filter((t) => t.model.toLowerCase().includes(model));
  }
  if (options?.status) {
    filtered = filtered.filter((t) => t.status === options.status);
  }

  filtered.sort(
    (a, b) =>
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );

  const offset = options?.offset ?? 0;
  const limit = options?.limit ?? filtered.length;
  return filtered.slice(offset, offset + limit);
}

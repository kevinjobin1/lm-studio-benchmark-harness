/**
 * Loader for workload evaluation results.
 *
 * Loads aggregated workload results from the prebuilt index at /workload-results.json
 * or from the filesystem at build time (SSR).
 */

// ── Types ─────────────────────────────────────────────────────────

export interface WorkloadResultEntry {
  model: string;
  provider: string;
  project: string;
  language: string;
  framework: string;
  timestamp: string;
  total_tasks: number;
  overall_score: number;
  total_time_ms: number;
  task_types: Record<string, number>;
  failures: Record<string, number>;
  strengths: Record<string, number>;
}

export interface WorkloadIndex {
  version: string;
  generated_at: string;
  total_entries: number;
  total_models: number;
  total_projects: number;
  total_tasks: number;
  mean_overall_score: number;
  entries: WorkloadResultEntry[];
}

export interface WorkloadModelSummary {
  model: string;
  provider: string;
  languages: string[];
  frameworks: string[];
  projects: string[];
  results: WorkloadResultEntry[];
  best_score: number;
  avg_score: number;
  total_tasks: number;
  last_run: string;
}

export interface WorkloadProjectSummary {
  project: string;
  language: string;
  framework: string;
  models: string[];
  results: WorkloadResultEntry[];
  best_score: number;
  avg_score: number;
  total_tasks: number;
}

// ── Loader ─────────────────────────────────────────────────────────

const WORKLOAD_RESULTS_URL = "/workload-results.json";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Load aggregated workload evaluation results.
 * At build time (SSR) reads from the filesystem.
 * At runtime fetches /workload-results.json.
 */
export async function loadWorkloadResults(): Promise<WorkloadIndex> {
  if (import.meta.env.SSR) {
    try {
      const fs = await import("fs");
      const path = await import("path");
      const filePath = path.resolve(process.cwd(), "public", "workload-results.json");
      const raw = fs.readFileSync(filePath, "utf-8");
      const data: WorkloadIndex = JSON.parse(raw);
      if (data.entries && data.entries.length > 0) {
        return data;
      }
      console.warn("workload-results.json has no entries.");
    } catch (err) {
      console.warn(
        `No workload-results.json at build time (${(err as Error).message || err}).`,
      );
    }
    return emptyIndex();
  }

  // Browser runtime: fetch over HTTP
  try {
    return await fetchJson<WorkloadIndex>(WORKLOAD_RESULTS_URL);
  } catch {
    console.warn("No workload-results.json found at runtime.");
    return emptyIndex();
  }
}

function emptyIndex(): WorkloadIndex {
  return {
    version: "1.0.0",
    generated_at: new Date().toISOString(),
    total_entries: 0,
    total_models: 0,
    total_projects: 0,
    total_tasks: 0,
    mean_overall_score: 0,
    entries: [],
  };
}

// ── Aggregation helpers ─────────────────────────────────────────────

/**
 * Group workload results by model for per-model summaries.
 */
export function groupByModel(index: WorkloadIndex): WorkloadModelSummary[] {
  const byModel = new Map<string, WorkloadResultEntry[]>();

  for (const entry of index.entries) {
    if (!byModel.has(entry.model)) {
      byModel.set(entry.model, []);
    }
    byModel.get(entry.model)!.push(entry);
  }

  const summaries: WorkloadModelSummary[] = [];

  for (const [model, results] of byModel) {
    const scores = results.map((r) => r.overall_score);
    summaries.push({
      model,
      provider: results[0].provider,
      languages: [...new Set(results.map((r) => r.language).filter(Boolean))],
      frameworks: [...new Set(results.map((r) => r.framework).filter(Boolean))],
      projects: [...new Set(results.map((r) => r.project))],
      results,
      best_score: Math.max(...scores),
      avg_score: scores.reduce((a, b) => a + b, 0) / scores.length,
      total_tasks: results.reduce((a, r) => a + r.total_tasks, 0),
      last_run: [...results]
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0]
        ?.timestamp || "",
    });
  }

  summaries.sort((a, b) => b.avg_score - a.avg_score);
  return summaries;
}

/**
 * Group workload results by project.
 */
export function groupByProject(index: WorkloadIndex): WorkloadProjectSummary[] {
  const byProject = new Map<string, WorkloadResultEntry[]>();

  for (const entry of index.entries) {
    if (!byProject.has(entry.project)) {
      byProject.set(entry.project, []);
    }
    byProject.get(entry.project)!.push(entry);
  }

  const summaries: WorkloadProjectSummary[] = [];

  for (const [project, results] of byProject) {
    const scores = results.map((r) => r.overall_score);
    summaries.push({
      project,
      language: results[0].language,
      framework: results[0].framework,
      models: [...new Set(results.map((r) => r.model))],
      results,
      best_score: Math.max(...scores),
      avg_score: scores.reduce((a, b) => a + b, 0) / scores.length,
      total_tasks: results.reduce((a, r) => a + r.total_tasks, 0),
    });
  }

  summaries.sort((a, b) => b.avg_score - a.avg_score);
  return summaries;
}

/**
 * Shared trace types used across the dashboard (V2).
 *
 * Extracted from TraceTimeline.tsx to break circular dependencies
 * between components, loaders, and persistence helpers.
 */

/** A single step within an execution trace. */
export interface TraceStep {
  id: string;
  type: "tool_call" | "reasoning" | "response" | "system" | "error" | "prompt" | "token";
  label: string;
  detail?: string;
  timing_ms: number;
  tool?: string;
  input?: string;
  output?: string;
  status: "success" | "failure" | "pending";
}

/** A complete execution trace run. */
export interface TraceRun {
  /** Schema version (semver). Dashboard reads this for forward-compat migrations. */
  version?: string;
  id: string;
  model: string;
  pack: string;
  prompt: string;
  timestamp: string;
  totalTimeMs: number;
  status: "completed" | "failed" | "running";
  steps: TraceStep[];
}

/** Material icon names for each step type. */
export const stepIcons: Record<string, string> = {
  system: "settings",
  prompt: "edit_note",
  tool_call: "build",
  token: "text_fields",
  reasoning: "psychology",
  response: "chat",
  error: "error",
};

/** CSS color variable references for each step type. */
export const stepColors: Record<string, string> = {
  system: "var(--text-tertiary)",
  prompt: "var(--text-secondary)",
  tool_call: "var(--brand-primary)",
  token: "var(--brand-primary)",
  reasoning: "var(--warning)",
  response: "var(--success)",
  error: "var(--error)",
};

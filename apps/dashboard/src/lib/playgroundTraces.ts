/**
 * Playground trace persistence helpers (V2).
 *
 * Provides a localStorage-backed store for traces captured during
 * interactive MCP playground sessions. Shared between PlaygroundApp
 * (producer) and TraceTimeline (consumer) without circular imports.
 */

import type { TraceRun } from "./traceTypes";

/** localStorage key for playground-captured traces. */
export const PLAYGROUND_TRACES_KEY = "model-lens-playground-traces";

/** Read all playground-captured traces from localStorage. */
export function loadPlaygroundTraces(): TraceRun[] {
  try {
    const raw = localStorage.getItem(PLAYGROUND_TRACES_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as TraceRun[];
  } catch {
    return [];
  }
}

/**
 * Persist a new trace to localStorage, prepending it and capping at 50 entries.
 * Returns the updated array.
 */
export function savePlaygroundTrace(trace: TraceRun): TraceRun[] {
  try {
    const existing = loadPlaygroundTraces();
    const merged = [trace, ...existing].slice(0, 50);
    localStorage.setItem(PLAYGROUND_TRACES_KEY, JSON.stringify(merged));
    return merged;
  } catch {
    return [];
  }
}

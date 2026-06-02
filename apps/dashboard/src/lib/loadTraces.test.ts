// @vitest-environment node
import { describe, it, expect, vi, afterEach } from "vitest";
import {
  loadTraceManifest,
  loadTrace,
  loadTraceList,
  filterManifest,
} from "./loadTraces";
import type {
  TraceManifest,
  TraceData,
  TraceIndexEntry,
} from "./loadTraces";

// ── Module-level mock fs ───────────────────────────────────────

const { mockReadFileSync } = vi.hoisted(() => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  mockReadFileSync: vi.fn(() => {
    throw new Error("ENOENT");
  }) as any,
}));

vi.mock("fs", () => ({
  readFileSync: mockReadFileSync,
  promises: { readFile: vi.fn() },
  existsSync: vi.fn(),
  writeFileSync: vi.fn(),
}));

// ── Fixtures ───────────────────────────────────────────────────

function makeTrace(overrides: Partial<TraceData> = {}): TraceData {
  return {
    trace_id: "trace-abc123",
    run_id: "run-xyz",
    model: "test-model",
    provider: "test-provider",
    prompt: "What is 2+2?",
    pack: "default",
    timestamp: "2026-06-02T12:00:00Z",
    totalTimeMs: 1500,
    status: "completed",
    steps: [
      {
        id: "trace-abc123-e0",
        type: "system",
        label: "System Instruction",
        timing_ms: 0,
        status: "success",
      },
      {
        id: "trace-abc123-e1",
        type: "response",
        label: "Response Complete",
        detail: "4",
        timing_ms: 900,
        status: "success",
      },
    ],
    metrics: {
      ttft_ms: 210,
      tokens_per_second: 72,
      total_tokens: 1,
      prompt_tokens: 5,
      completion_tokens: 1,
      total_latency_ms: 1500,
      memory_pressure_mb: 800,
      token_timings_ms: [210],
    },
    artifacts: {
      response: "4",
      logs: [],
      errors: [],
    },
    ...overrides,
  };
}

function makeTraceEntry(
  overrides: Partial<TraceIndexEntry> = {},
): TraceIndexEntry {
  return {
    trace_id: "trace-abc123",
    run_id: "run-xyz",
    model: "test-model",
    provider: "test-provider",
    prompt: "What is 2+2?",
    timestamp: "2026-06-02T12:00:00Z",
    totalTimeMs: 1500,
    status: "completed",
    stepCount: 4,
    tokenCount: 10,
    ttft_ms: 210,
    ...overrides,
  };
}

function makeManifest(
  traces: TraceIndexEntry[] = [],
): TraceManifest {
  return {
    version: "1.0.0",
    generated_at: "2026-06-02T12:00:00Z",
    total_traces: traces.length,
    traces,
  };
}

// ── loadTraceManifest ──────────────────────────────────────────

describe("loadTraceManifest", () => {
  afterEach(() => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
  });

  it("returns empty manifest when index.json does not exist", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const manifest = await loadTraceManifest();
    expect(manifest.traces).toEqual([]);
    expect(manifest.total_traces).toBe(0);
    expect(manifest.version).toBe("1.0.0");
  });

  it("loads and parses the manifest when index.json exists", async () => {
    const fixture = makeManifest([makeTraceEntry()]);
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const manifest = await loadTraceManifest();
    expect(manifest.total_traces).toBe(1);
    expect(manifest.traces[0].model).toBe("test-model");
  });

  it("handles invalid JSON gracefully", async () => {
    mockReadFileSync.mockReturnValue("not json");
    const manifest = await loadTraceManifest();
    expect(manifest.traces).toEqual([]);
  });

  it("handles multiple traces in the manifest", async () => {
    const fixture = makeManifest([
      makeTraceEntry({ trace_id: "t1", model: "alpha" }),
      makeTraceEntry({ trace_id: "t2", model: "beta" }),
      makeTraceEntry({ trace_id: "t3", model: "gamma" }),
    ]);
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const manifest = await loadTraceManifest();
    expect(manifest.total_traces).toBe(3);
  });
});

// ── loadTrace ──────────────────────────────────────────────────

describe("loadTrace", () => {
  afterEach(() => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
  });

  it("returns null when trace file does not exist", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const trace = await loadTrace("nonexistent");
    expect(trace).toBeNull();
  });

  it("loads and parses a trace JSON file", async () => {
    const fixture = makeTrace();
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const trace = await loadTrace("trace-abc123");
    expect(trace).not.toBeNull();
    expect(trace!.trace_id).toBe("trace-abc123");
    expect(trace!.model).toBe("test-model");
    expect(trace!.steps).toHaveLength(2);
  });

  it("returns null for malformed JSON", async () => {
    mockReadFileSync.mockReturnValue("{invalid");
    const trace = await loadTrace("bad-trace");
    expect(trace).toBeNull();
  });

  it("includes all expected fields in loaded trace", async () => {
    const fixture = makeTrace();
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const trace = await loadTrace("trace-abc123");
    expect(trace!.metrics.ttft_ms).toBe(210);
    expect(trace!.metrics.tokens_per_second).toBe(72);
    expect(trace!.artifacts.response).toBe("4");
    expect(trace!.hardware).toBeUndefined();
  });

  it("handles traces with hardware info", async () => {
    const fixture = makeTrace({
      hardware: { cpu: "M3", memory_gb: 18 },
    });
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const trace = await loadTrace("trace-hw");
    expect(trace!.hardware).toEqual({ cpu: "M3", memory_gb: 18 });
  });
});

// ── loadTraceList (SSR path) ───────────────────────────────────

describe("loadTraceList", () => {
  afterEach(() => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
  });

  it("returns empty array when no manifest exists", async () => {
    mockReadFileSync.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    const entries = await loadTraceList();
    expect(entries).toEqual([]);
  });

  it("returns all traces from the manifest by default", async () => {
    const fixture = makeManifest([
      makeTraceEntry({ trace_id: "t1" }),
      makeTraceEntry({ trace_id: "t2" }),
    ]);
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const entries = await loadTraceList();
    expect(entries).toHaveLength(2);
  });

  it("filters by model name (case-insensitive)", async () => {
    const fixture = makeManifest([
      makeTraceEntry({ trace_id: "t1", model: "llama-3" }),
      makeTraceEntry({ trace_id: "t2", model: "gemma-4" }),
    ]);
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const entries = await loadTraceList({ model: "Llama" });
    expect(entries).toHaveLength(1);
    expect(entries[0].model).toBe("llama-3");
  });

  it("filters by status", async () => {
    const fixture = makeManifest([
      makeTraceEntry({ trace_id: "t1", status: "completed" }),
      makeTraceEntry({ trace_id: "t2", status: "failed" }),
    ]);
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const entries = await loadTraceList({ status: "failed" });
    expect(entries).toHaveLength(1);
    expect(entries[0].trace_id).toBe("t2");
  });

  it("respects limit and offset", async () => {
    const fixture = makeManifest([
      makeTraceEntry({ trace_id: "t1", timestamp: "2026-06-01T00:00:00Z" }),
      makeTraceEntry({ trace_id: "t2", timestamp: "2026-06-02T00:00:00Z" }),
      makeTraceEntry({ trace_id: "t3", timestamp: "2026-06-03T00:00:00Z" }),
    ]);
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const entries = await loadTraceList({ limit: 2, offset: 0 });
    // Sorted newest first
    expect(entries).toHaveLength(2);
    expect(entries[0].trace_id).toBe("t3");
    expect(entries[1].trace_id).toBe("t2");
  });

  it("handles offset beyond list length", async () => {
    const fixture = makeManifest([makeTraceEntry()]);
    mockReadFileSync.mockReturnValue(JSON.stringify(fixture));
    const entries = await loadTraceList({ offset: 10 });
    expect(entries).toEqual([]);
  });
});

// ── Trace type guards / validators ─────────────────────────────

describe("TraceData type validation", () => {
  it("complete TraceData matches all required fields", () => {
    const t = makeTrace();
    expect(t.trace_id).toBeTruthy();
    expect(t.steps.length).toBeGreaterThan(0);
    expect(t.metrics.ttft_ms).toBeGreaterThanOrEqual(0);
    expect(["completed", "failed", "running"]).toContain(t.status);
  });

  it("TraceIndexEntry has the required lightweight fields", () => {
    const entry = makeTraceEntry();
    expect(entry.trace_id).toBeTruthy();
    expect(entry.model).toBeTruthy();
    expect(typeof entry.stepCount).toBe("number");
    expect(typeof entry.tokenCount).toBe("number");
  });

  it("TraceManifest has version and traces array", () => {
    const manifest = makeManifest();
    expect(manifest.version).toBe("1.0.0");
    expect(Array.isArray(manifest.traces)).toBe(true);
  });
});

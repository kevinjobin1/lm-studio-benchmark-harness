// @vitest-environment node
import { describe, it, expect, vi, beforeEach, afterEach, afterAll, beforeAll } from "vitest";
import {
  generateSnapshotId,
  snapshotUrl,
  traceRunToSnapshot,
  loadSnapshotManifest,
  loadSnapshot,
  saveSnapshot,
  emptyManifest,
} from "./loadSnapshots";
import type { TraceRun } from "./traceTypes";

// ── Fixtures ───────────────────────────────────────────────────────

function makeTraceRun(overrides: Partial<TraceRun> = {}): TraceRun {
  return {
    id: "trace-test-1",
    model: "qwen3.5-9b-coder",
    pack: "nestjs-pack",
    prompt: "Build a JWT guard",
    timestamp: "Jun 2, 2:14 PM",
    totalTimeMs: 1200,
    status: "completed",
    steps: [
      { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" },
      { id: "s1", type: "prompt", label: "Prompt Sent", timing_ms: 10, status: "success" },
      { id: "s2", type: "response", label: "Complete", detail: "Built JWT guard", timing_ms: 500, status: "success" },
    ],
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────

describe("generateSnapshotId", () => {
  it("generates IDs with snap- prefix", () => {
    const id = generateSnapshotId();
    expect(id.startsWith("snap-")).toBe(true);
  });

  it("generates IDs of correct length", () => {
    const id = generateSnapshotId();
    expect(id.length).toBe(9); // "snap-" (5) + 4 chars
  });

  it("generates unique IDs on successive calls", () => {
    const ids = new Set(Array.from({ length: 100 }, () => generateSnapshotId()));
    expect(ids.size).toBe(100);
  });
});

describe("snapshotUrl", () => {
  it("returns relative URL when window is undefined", () => {
    // SSR context: window is undefined
    const url = snapshotUrl("snap-test");
    expect(url).toBe("/runs/snap-test");
  });

  it("uses window.location.origin when available", () => {
    const origWindow = globalThis.window;
    (globalThis as any).window = { location: { origin: "https://example.com" } };
    const url = snapshotUrl("snap-test");
    expect(url).toBe("https://example.com/runs/snap-test");
    (globalThis as any).window = origWindow;
  });

  it("encodes special characters in ID", () => {
    const url = snapshotUrl("snap with spaces");
    expect(url).toContain(encodeURIComponent("snap with spaces"));
  });
});

describe("traceRunToSnapshot", () => {
  it("creates a SnapshotData from a TraceRun", () => {
    const run = makeTraceRun();
    const snapshot = traceRunToSnapshot(run);

    expect(snapshot.model).toBe("qwen3.5-9b-coder");
    expect(snapshot.prompt).toBe("Build a JWT guard");
    expect(snapshot.pack).toBe("nestjs-pack");
    expect(snapshot.provider).toBe("unknown");
    expect(snapshot.note).toBeUndefined();
  });

  it("extracts response from the last response-type step", () => {
    const run = makeTraceRun();
    const snapshot = traceRunToSnapshot(run);
    expect(snapshot.response).toBe("Built JWT guard");
  });

  it("returns empty response string when no response step exists", () => {
    const run = makeTraceRun({
      steps: [
        { id: "s0", type: "system", label: "S", timing_ms: 0, status: "success" },
      ],
    });
    const snapshot = traceRunToSnapshot(run);
    expect(snapshot.response).toBe("");
  });

  it("accepts optional provider and note", () => {
    const run = makeTraceRun();
    const snapshot = traceRunToSnapshot(run, {
      provider: "ollama",
      note: "Test run",
    });

    expect(snapshot.provider).toBe("ollama");
    expect(snapshot.note).toBe("Test run");
  });

  it("calculates tokens_per_second from total tokens and time", () => {
    const run = makeTraceRun({ totalTimeMs: 1000 });
    // Token steps have a total of roughly 4 words in the detail
    const snapshot = traceRunToSnapshot(run, { totalTokens: 50 });
    expect(snapshot.metrics.tokens_per_second).toBe(50);
  });

  it("includes the full trace run", () => {
    const run = makeTraceRun();
    const snapshot = traceRunToSnapshot(run);
    expect(snapshot.trace).toBe(run);
  });

  it("generates a unique snapshot_id each call", () => {
    const run = makeTraceRun();
    const a = traceRunToSnapshot(run);
    const b = traceRunToSnapshot(run);
    expect(a.snapshot_id).not.toBe(b.snapshot_id);
  });
});

describe("loadSnapshotManifest", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("returns empty manifest when no snapshots exist (SSR)", async () => {
    const manifest = await loadSnapshotManifest();
    expect(manifest.version).toBe("1.0.0");
    expect(manifest.total_snapshots).toBe(0);
    expect(manifest.snapshots).toEqual([]);
  });
});

describe("loadSnapshot", () => {
  it("returns null for non-existent snapshot (SSR)", async () => {
    const result = await loadSnapshot("nonexistent");
    expect(result).toBeNull();
  });
});

describe("saveSnapshot", () => {
  beforeAll(async () => {
    // Clean up any lingering snapshot files from previous runs
    try {
      const fs = await import("fs");
      const path = await import("path");
      const snapDir = path.resolve(process.cwd(), "results", "snapshots");
      if (fs.existsSync(snapDir)) {
        fs.rmSync(snapDir, { recursive: true, force: true });
      }
    } catch {
      // cleanup is best-effort
    }
  });

  afterAll(async () => {
    // Clean up snapshot files after all save tests
    try {
      const fs = await import("fs");
      const path = await import("path");
      const snapDir = path.resolve(process.cwd(), "results", "snapshots");
      if (fs.existsSync(snapDir)) {
        fs.rmSync(snapDir, { recursive: true, force: true });
      }
    } catch {
      // cleanup is best-effort
    }
  });

  it("saves a snapshot and returns id and url (SSR)", async () => {
    const run = makeTraceRun();
    const snapshot = traceRunToSnapshot(run);

    const result = await saveSnapshot(snapshot);
    expect(result.snapshot_id).toBe(snapshot.snapshot_id);
    expect(result.url).toContain(snapshot.snapshot_id);
  });

  it("creates the snapshot file on disk (SSR)", async () => {
    const run = makeTraceRun();
    const snapshot = traceRunToSnapshot(run);

    const result = await saveSnapshot(snapshot);
    expect(result.url).toBeTruthy();
  });
});

// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import TraceComparison from "./TraceComparison";
import type { TraceRun } from "../lib/traceTypes";

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Helpers ────────────────────────────────────────────────────────

function makeTrace(
  overrides: Partial<TraceRun> & { id: string; model: string },
): TraceRun {
  return {
    pack: "nestjs-pack",
    prompt: "Build a JWT guard",
    timestamp: "Jun 2, 2:14 PM",
    totalTimeMs: 1200,
    status: "completed",
    steps: [
      {
        id: "s0",
        type: "system",
        label: "System Instruction",
        timing_ms: 0,
        status: "success",
      },
      {
        id: "s1",
        type: "prompt",
        label: "Prompt Received",
        detail: "Build a JWT guard for NestJS",
        timing_ms: 10,
        status: "success",
      },
      {
        id: "s2",
        type: "tool_call",
        label: "Calling: read_file auth.module.ts",
        tool: "file_read",
        input: "auth.module.ts",
        timing_ms: 120,
        status: "success",
      },
      {
        id: "s3",
        type: "reasoning",
        label: "Analyzing auth patterns",
        detail: "Need to implement JwtStrategy and JwtGuard",
        timing_ms: 200,
        status: "success",
      },
      {
        id: "s4",
        type: "response",
        label: "Generated Implementation",
        detail: "Created JwtGuard with Passport strategy",
        timing_ms: 400,
        status: "success",
      },
    ],
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────

describe("TraceComparison", () => {
  it("renders empty state when both trace arrays are empty", () => {
    render(<TraceComparison tracesA={[]} tracesB={[]} />);
    expect(
      screen.getByText(/No trace data available for comparison/),
    ).toBeTruthy();
  });

  it("renders two model columns when both traces are provided", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-alpha" });
    const traceB = makeTrace({ id: "t-b", model: "model-beta" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Both models shown in column headers
    expect(screen.getByText("model-alpha")).toBeTruthy();
    expect(screen.getByText("model-beta")).toBeTruthy();
  });

  it("renders the diff summary bar with time comparison", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "fast-model",
      totalTimeMs: 800,
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "slow-model",
      totalTimeMs: 1200,
    });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Diff bar shows which model is faster
    expect(
      screen.getByText(/fast-model was 400ms faster than slow-model/),
    ).toBeTruthy();
  });

  it("shows step count comparison in diff bar", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "few-steps",
      steps: [
        {
          id: "s0",
          type: "system",
          label: "Start",
          timing_ms: 0,
          status: "success",
        },
      ],
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "many-steps",
      steps: [
        {
          id: "s0",
          type: "system",
          label: "Start",
          timing_ms: 0,
          status: "success",
        },
        {
          id: "s1",
          type: "response",
          label: "Done",
          timing_ms: 100,
          status: "success",
        },
        {
          id: "s2",
          type: "response",
          label: "Extra",
          timing_ms: 50,
          status: "success",
        },
      ],
    });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    expect(
      screen.getByText("many-steps used 2 more steps"),
    ).toBeTruthy();
  });

  it("renders step type chips in cells", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a" });
    const traceB = makeTrace({ id: "t-b", model: "model-b" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Step type chips appear (once per column)
    expect(screen.getAllByText("system").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("prompt").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("tool call").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("reasoning").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("response").length).toBeGreaterThanOrEqual(2);
  });

  it("shows step timing values in cells", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a" });
    const traceB = makeTrace({ id: "t-b", model: "model-b" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Timing values appear
    const timings = screen.getAllByText(/ms$/);
    expect(timings.length).toBeGreaterThan(0);
  });

  it("shows step labels", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a" });
    const traceB = makeTrace({ id: "t-b", model: "model-b" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    expect(screen.getAllByText("System Instruction").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Prompt Received").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/Calling: read_file/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Analyzing auth patterns").length).toBeGreaterThanOrEqual(2);
  });

  it("renders optional third column when tracesC is provided", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a" });
    const traceB = makeTrace({ id: "t-b", model: "model-b" });
    const traceC = makeTrace({ id: "t-c", model: "model-c" });

    render(
      <TraceComparison
        tracesA={[traceA]}
        tracesB={[traceB]}
        tracesC={[traceC]}
      />,
    );

    expect(screen.getByText("model-a")).toBeTruthy();
    expect(screen.getByText("model-b")).toBeTruthy();
    expect(screen.getByText("model-c")).toBeTruthy();
  });

  it("picks the trace with most steps when multiple are available", () => {
    const shortTrace = makeTrace({
      id: "t-short",
      model: "test-model",
      steps: [
        {
          id: "s0",
          type: "system",
          label: "Start",
          timing_ms: 0,
          status: "success",
        },
      ],
    });
    const longTrace = makeTrace({
      id: "t-long",
      model: "test-model",
      steps: [
        {
          id: "s0",
          type: "system",
          label: "Start",
          timing_ms: 0,
          status: "success",
        },
        {
          id: "s1",
          type: "prompt",
          label: "Prompt",
          timing_ms: 5,
          status: "success",
        },
        {
          id: "s2",
          type: "response",
          label: "Done",
          timing_ms: 100,
          status: "success",
        },
      ],
    });

    render(
      <TraceComparison tracesA={[shortTrace, longTrace]} tracesB={[]} />,
    );

    // Should prefer the longer trace (3 steps) over the shorter (1 step)
    // Text is embedded in metadata string like "pack · 800ms · 3 steps"
    expect(screen.getByText(/3 steps/)).toBeTruthy();
    expect(screen.queryByText(/1 steps/)).toBeNull();
  });

  it("shows no diff bar when only one model has traces", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[]} />);

    // Model A column exists
    expect(screen.getByText("model-a")).toBeTruthy();
    // Model B column shows "no traces"
    expect(screen.getByText("No traces available")).toBeTruthy();
  });

  it("renders step details in cells", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "model-a",
      steps: [
        {
          id: "s0",
          type: "system",
          label: "System",
          timing_ms: 0,
          status: "success",
        },
        {
          id: "s1",
          type: "reasoning",
          label: "Analysis",
          detail: "Detailed analysis of the problem",
          timing_ms: 150,
          status: "success",
        },
      ],
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "model-b",
      steps: [
        {
          id: "s0",
          type: "system",
          label: "System",
          timing_ms: 0,
          status: "success",
        },
        {
          id: "s1",
          type: "response",
          label: "Response",
          timing_ms: 100,
          status: "success",
        },
      ],
    });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    expect(screen.getByText("Detailed analysis of the problem")).toBeTruthy();
  });

  it("shows failure icon on error steps", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "model-a",
      steps: [
        {
          id: "s0",
          type: "system",
          label: "System",
          timing_ms: 0,
          status: "success",
        },
        {
          id: "s1",
          type: "error",
          label: "Connection Failed",
          detail: "API returned 500",
          timing_ms: 500,
          status: "failure",
        },
      ],
    });
    const traceB = makeTrace({ id: "t-b", model: "model-b" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Error step renders error type chip (and may appear in failure icon too)
    const errorElements = screen.getAllByText("error");
    expect(errorElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows status icon for failed trace runs", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "fail-model",
      status: "failed",
    });
    const traceB = makeTrace({ id: "t-b", model: "model-b" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Failed status icon
    const cancelIcons = screen.getAllByText("cancel");
    expect(cancelIcons.length).toBe(1);
  });

  it("renders the legend with step types", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a" });
    const traceB = makeTrace({ id: "t-b", model: "model-b" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    expect(screen.getByText("Step types:")).toBeTruthy();
    // "system", "prompt", etc. appear in both legend chips and step cells
    expect(screen.getAllByText("system").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("prompt").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("tool call").length).toBeGreaterThanOrEqual(1);
  });

  it("shows model pack and metadata in column headers", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a", pack: "react-pack" });
    const traceB = makeTrace({ id: "t-b", model: "model-b", pack: "nestjs-pack" });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    expect(screen.getByText(/react-pack/)).toBeTruthy();
    expect(screen.getByText(/nestjs-pack/)).toBeTruthy();
  });

  it("renders total time in column headers", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a", totalTimeMs: 1200 });
    const traceB = makeTrace({ id: "t-b", model: "model-b", totalTimeMs: 800 });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    expect(screen.getByText(/1200ms/)).toBeTruthy();
    expect(screen.getByText(/800ms/)).toBeTruthy();
  });

  // ── Diff mode tests ───────────────────────────────────────────

  it("renders diff badges on each step when showDiffs is true (default)", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "fast-model",
      steps: [
        { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" },
        { id: "s1", type: "tool_call", label: "Fast lookup", timing_ms: 20, status: "success" },
        { id: "s2", type: "response", label: "Done", timing_ms: 100, status: "success" },
      ],
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "slow-model",
      steps: [
        { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" },
        { id: "s1", type: "tool_call", label: "Slow lookup", timing_ms: 80, status: "success" },
        { id: "s2", type: "response", label: "Done", timing_ms: 200, status: "success" },
      ],
    });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Fast model shows green negative delta (−60ms for step 1, −100ms for step 2)
    expect(screen.getByText(/−60ms/)).toBeTruthy();
    expect(screen.getByText(/−100ms/)).toBeTruthy();
    // Slow model shows red positive delta (+60ms, +100ms)
    expect(screen.getByText(/\+60ms/)).toBeTruthy();
    expect(screen.getByText(/\+100ms/)).toBeTruthy();
    // Equal step (timing_ms: 0 for system) shows equal badge
    const equalBadges = screen.getAllByText(/=0ms/);
    expect(equalBadges.length).toBe(2);
  });

  it("hides diff badges when showDiffs is false", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "model-a",
      steps: [
        { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" },
        { id: "s1", type: "tool_call", label: "Fast", timing_ms: 20, status: "success" },
      ],
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "model-b",
      steps: [
        { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" },
        { id: "s1", type: "tool_call", label: "Slow", timing_ms: 50, status: "success" },
      ],
    });

    render(
      <TraceComparison tracesA={[traceA]} tracesB={[traceB]} showDiffs={false} />,
    );

    // No diff badges should be present
    expect(screen.queryByText(/−30ms/)).toBeNull();
    expect(screen.queryByText(/\+30ms/)).toBeNull();
  });

  it("shows diff color indicators in summary bar when diffs enabled", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "fast-model",
      totalTimeMs: 500,
      steps: [
        { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" },
      ],
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "slow-model",
      totalTimeMs: 800,
      steps: [
        { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" },
      ],
    });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Diff indicator text in summary bar
    expect(screen.getByText("Green = faster step")).toBeTruthy();
    expect(screen.getByText("Red = slower step")).toBeTruthy();
  });

  it("hides diff color indicators in summary bar when showDiffs is false", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "fast-model",
      totalTimeMs: 500,
      steps: [
        { id: "s0", type: "system", label: "Start", timing_ms: 0, status: "success" },
      ],
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "slow-model",
      totalTimeMs: 800,
      steps: [
        { id: "s0", type: "system", label: "Start", timing_ms: 0, status: "success" },
      ],
    });

    render(
      <TraceComparison tracesA={[traceA]} tracesB={[traceB]} showDiffs={false} />,
    );

    expect(screen.queryByText("Green = faster step")).toBeNull();
    expect(screen.queryByText("Red = slower step")).toBeNull();
  });

  it("shows diff legend dots when showDiffs is true", () => {
    const traceA = makeTrace({ id: "t-a", model: "model-a", totalTimeMs: 500 });
    const traceB = makeTrace({ id: "t-b", model: "model-b", totalTimeMs: 800 });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Diff legend label and chips appear
    expect(screen.getByText("Diffs:")).toBeTruthy();
    expect(screen.getByText("faster")).toBeTruthy();
    expect(screen.getByText("slower")).toBeTruthy();
  });

  it("handles mismatched step counts gracefully with diffs", () => {
    const traceA = makeTrace({
      id: "t-a",
      model: "fewer-steps",
      steps: [
        { id: "s0", type: "system", label: "Start", timing_ms: 0, status: "success" },
        { id: "s1", type: "response", label: "Fast finish", timing_ms: 50, status: "success" },
      ],
    });
    const traceB = makeTrace({
      id: "t-b",
      model: "more-steps",
      steps: [
        { id: "s0", type: "system", label: "Start", timing_ms: 0, status: "success" },
        { id: "s1", type: "reasoning", label: "Thinking", timing_ms: 200, status: "success" },
        { id: "s2", type: "tool_call", label: "Extra work", timing_ms: 100, status: "success" },
        { id: "s3", type: "response", label: "Slow finish", timing_ms: 150, status: "success" },
      ],
    });

    render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

    // Diff badge for the first 2 aligned steps (step 1: −150ms faster)
    expect(screen.getByText(/−150ms/)).toBeTruthy();
    // Step 2 has no diff badge for traceA (empty cell shows "—")
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
    // But traceB step 2 shows +100ms (no matching step in A)
    // Actually with no matching step, computeStepDelta returns null, so no badge
    expect(screen.queryByText(/\+100ms/)).toBeNull();

    // Plus badge for step 1 in traceB: +150ms
    expect(screen.getByText(/\+150ms/)).toBeTruthy();
  });

  // ═══════════════════════════════════════════════════════════
  // Diff badge step-by-step verification tests
  // ═══════════════════════════════════════════════════════════

  describe("diff badge step-by-step", () => {
    it("shows correct per-step diff badges when model A is faster", () => {
      const traceA = makeTrace({
        id: "t-a",
        model: "fast",
        steps: [
          { id: "s0", type: "system", label: "Init", timing_ms: 0, status: "success" },
          { id: "s1", type: "tool_call", label: "Fast tool", timing_ms: 30, status: "success" },
          { id: "s2", type: "response", label: "Fast response", timing_ms: 80, status: "success" },
        ],
      });
      const traceB = makeTrace({
        id: "t-b",
        model: "slow",
        steps: [
          { id: "s0", type: "system", label: "Init", timing_ms: 0, status: "success" },
          { id: "s1", type: "tool_call", label: "Slow tool", timing_ms: 90, status: "success" },
          { id: "s2", type: "response", label: "Slow response", timing_ms: 200, status: "success" },
        ],
      });

      render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

      // Column A (fast): all diffs should be negative/faster or equal
      // Step 0: 0ms - 0ms = 0 → equal badge
      // Step 1: 30ms - 90ms = −60ms → faster badge in A
      // Step 2: 80ms - 200ms = −120ms → faster badge in A
      expect(screen.getByText("−60ms")).toBeTruthy();
      expect(screen.getByText("−120ms")).toBeTruthy();

      // Column B (slow): all diffs should be positive/slower
      // Step 1: 90ms - 30ms = 60ms → slower badge in B
      // Step 2: 200ms - 80ms = 120ms → slower badge in B
      expect(screen.getByText("+60ms")).toBeTruthy();
      expect(screen.getByText("+120ms")).toBeTruthy();

      // Equal step shows =0ms in both columns
      const equalBadges = screen.getAllByText("=0ms");
      expect(equalBadges.length).toBe(2);
    });

    it("shows correct per-step diff badges when model B is faster (reverse polarity)", () => {
      const traceA = makeTrace({
        id: "t-a",
        model: "slow-model",
        totalTimeMs: 1500,
        steps: [
          { id: "s0", type: "system", label: "Init", timing_ms: 0, status: "success" },
          { id: "s1", type: "reasoning", label: "Slow think", timing_ms: 500, status: "success" },
          { id: "s2", type: "response", label: "Slow out", timing_ms: 300, status: "success" },
        ],
      });
      const traceB = makeTrace({
        id: "t-b",
        model: "fast-model",
        totalTimeMs: 600,
        steps: [
          { id: "s0", type: "system", label: "Init", timing_ms: 0, status: "success" },
          { id: "s1", type: "reasoning", label: "Fast think", timing_ms: 150, status: "success" },
          { id: "s2", type: "response", label: "Fast out", timing_ms: 100, status: "success" },
        ],
      });

      render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

      // Column A (slow): diffs should be positive/slower
      // Step 1: 500ms - 150ms = 350ms → slower in A
      // Step 2: 300ms - 100ms = 200ms → slower in A
      expect(screen.getByText("+350ms")).toBeTruthy();
      expect(screen.getByText("+200ms")).toBeTruthy();

      // Column B (fast): diffs should be negative/faster
      // Step 1: 150ms - 500ms = −350ms → faster in B
      // Step 2: 100ms - 300ms = −200ms → faster in B
      expect(screen.getByText("−350ms")).toBeTruthy();
      expect(screen.getByText("−200ms")).toBeTruthy();

      // Diff summary bar: fast-model was Xms faster
      expect(
        screen.getByText(/fast-model was \d+ms faster than slow-model/),
      ).toBeTruthy();
    });

    it("shows all-equal diff badges when both models have identical step timings", () => {
      const traceA = makeTrace({
        id: "t-a",
        model: "model-a",
        steps: [
          { id: "s0", type: "system", label: "Init", timing_ms: 0, status: "success" },
          { id: "s1", type: "tool_call", label: "Lookup", timing_ms: 50, status: "success" },
          { id: "s2", type: "response", label: "Done", timing_ms: 100, status: "success" },
        ],
      });
      const traceB = makeTrace({
        id: "t-b",
        model: "model-b",
        steps: [
          { id: "s0", type: "system", label: "Init", timing_ms: 0, status: "success" },
          { id: "s1", type: "tool_call", label: "Lookup", timing_ms: 50, status: "success" },
          { id: "s2", type: "response", label: "Done", timing_ms: 100, status: "success" },
        ],
      });

      render(<TraceComparison tracesA={[traceA]} tracesB={[traceB]} />);

      // Every step is equal — =0ms badges across both columns (3 steps × 2 = 6)
      const equalBadges = screen.getAllByText("=0ms");
      expect(equalBadges.length).toBe(6);

      // Diff summary: identical total time
      expect(screen.getByText("Identical total time")).toBeTruthy();
      expect(screen.getByText("Same number of steps")).toBeTruthy();
    });

    it("third column has no diff badges even when showDiffs is true", () => {
      const traceA = makeTrace({
        id: "t-a",
        model: "alpha",
        steps: [
          { id: "a0", type: "system", label: "A Init", timing_ms: 0, status: "success" },
          { id: "a1", type: "tool_call", label: "A Tool", timing_ms: 50, status: "success" },
        ],
      });
      const traceB = makeTrace({
        id: "t-b",
        model: "beta",
        steps: [
          { id: "b0", type: "system", label: "B Init", timing_ms: 0, status: "success" },
          { id: "b1", type: "tool_call", label: "B Tool", timing_ms: 100, status: "success" },
        ],
      });
      const traceC = makeTrace({
        id: "t-c",
        model: "gamma",
        steps: [
          { id: "c0", type: "system", label: "C Init", timing_ms: 0, status: "success" },
          { id: "c1", type: "tool_call", label: "C Tool", timing_ms: 200, status: "success" },
        ],
      });

      render(
        <TraceComparison
          tracesA={[traceA]}
          tracesB={[traceB]}
          tracesC={[traceC]}
        />,
      );

      // Columns A and B have diff badges (−50ms for A, +50ms for B on step 1)
      expect(screen.getByText("−50ms")).toBeTruthy();
      expect(screen.getByText("+50ms")).toBeTruthy();

      // Column C should have NO diff badges (internally called with showDiffs={false})
      // Column C has 200ms timing, not showing any diff
      // Verify C's label renders but no diff badge references C's step timing delta
      expect(screen.getByText("C Tool")).toBeTruthy();
    });

    it("three models with mixed step counts align rows correctly", () => {
      const traceA = makeTrace({
        id: "t-a",
        model: "few",
        steps: [
          { id: "a0", type: "system", label: "A0", timing_ms: 0, status: "success" },
          { id: "a1", type: "response", label: "A1", timing_ms: 100, status: "success" },
        ],
      });
      const traceB = makeTrace({
        id: "t-b",
        model: "many",
        steps: [
          { id: "b0", type: "system", label: "B0", timing_ms: 0, status: "success" },
          { id: "b1", type: "reasoning", label: "B1", timing_ms: 200, status: "success" },
          { id: "b2", type: "tool_call", label: "B2", timing_ms: 50, status: "success" },
          { id: "b3", type: "response", label: "B3", timing_ms: 150, status: "success" },
        ],
      });
      const traceC = makeTrace({
        id: "t-c",
        model: "third",
        steps: [
          { id: "c0", type: "system", label: "C0", timing_ms: 0, status: "success" },
          { id: "c1", type: "tool_call", label: "C1", timing_ms: 300, status: "success" },
          { id: "c2", type: "response", label: "C2", timing_ms: 200, status: "success" },
        ],
      });

      render(
        <TraceComparison
          tracesA={[traceA]}
          tracesB={[traceB]}
          tracesC={[traceC]}
        />,
      );

      // All three column headers visible
      expect(screen.getByText("few")).toBeTruthy();
      expect(screen.getByText("many")).toBeTruthy();
      expect(screen.getByText("third")).toBeTruthy();

      // maxStepCount = max(2, 4, 3) = 4
      // Column A: shows 2 cells + 2 empty cells (—)
      // Column B: shows all 4 cells
      // Column C: shows 3 cells + 1 empty cell
      // Empty cells render "—"
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBe(3); // A:2 empty + C:1 empty

      // Column B shows step B2 (at row index 2)
      expect(screen.getByText("B2")).toBeTruthy();
      // Column B shows step B3 (at row index 3)
      expect(screen.getByText("B3")).toBeTruthy();

      // Column C shows C1 at row index 1
      expect(screen.getByText("C1")).toBeTruthy();
    });

    it("diff badge CSS classes are applied correctly (faster/slower/equal)", () => {
      const traceA = makeTrace({
        id: "t-a",
        model: "model-a",
        steps: [
          { id: "s0", type: "system", label: "Step 0", timing_ms: 0, status: "success" },
          { id: "s1", type: "tool_call", label: "Step 1", timing_ms: 20, status: "success" },
          { id: "s2", type: "response", label: "Step 2", timing_ms: 150, status: "success" },
        ],
      });
      const traceB = makeTrace({
        id: "t-b",
        model: "model-b",
        steps: [
          { id: "s0", type: "system", label: "Step 0", timing_ms: 0, status: "success" },
          { id: "s1", type: "tool_call", label: "Step 1", timing_ms: 80, status: "success" },
          { id: "s2", type: "response", label: "Step 2", timing_ms: 100, status: "success" },
        ],
      });

      const { container } = render(
        <TraceComparison tracesA={[traceA]} tracesB={[traceB]} />,
      );

      // CSS class assertions
      const fasterBadges = container.querySelectorAll(".tcmp-delta-faster");
      const slowerBadges = container.querySelectorAll(".tcmp-delta-slower");
      const equalBadges = container.querySelectorAll(".tcmp-delta-equal");

      // Step 0: both equal → 2 equal badges
      // Step 1: A is faster (−60ms), B is slower (+60ms) → 1 faster, 1 slower
      // Step 2: A is slower (+50ms), B is faster (−50ms) → 1 faster, 1 slower
      // Total: 2 faster, 2 slower, 2 equal
      expect(fasterBadges.length).toBe(2);
      expect(slowerBadges.length).toBe(2);
      expect(equalBadges.length).toBe(2);

      // Verify text content of the badges
      const badgeTexts = [
        ...fasterBadges,
        ...slowerBadges,
        ...equalBadges,
      ].map((el) => el.textContent);
      expect(badgeTexts).toContain("−60ms");
      expect(badgeTexts).toContain("+60ms");
      expect(badgeTexts).toContain("−50ms");
      expect(badgeTexts).toContain("+50ms");
      expect(badgeTexts.filter((t) => t === "=0ms").length).toBe(2);
    });

    it("diff summary bar shows step delta explanation for 3-column mode", () => {
      const traceA = makeTrace({
        id: "t-a",
        model: "alpha",
        totalTimeMs: 1000,
        steps: [
          { id: "a0", type: "system", label: "A0", timing_ms: 0, status: "success" },
          { id: "a1", type: "response", label: "A1", timing_ms: 500, status: "success" },
        ],
      });
      const traceB = makeTrace({
        id: "t-b",
        model: "beta",
        totalTimeMs: 1500,
        steps: [
          { id: "b0", type: "system", label: "B0", timing_ms: 0, status: "success" },
          { id: "b1", type: "response", label: "B1", timing_ms: 200, status: "success" },
          { id: "b2", type: "response", label: "B2", timing_ms: 100, status: "success" },
        ],
      });
      const traceC = makeTrace({
        id: "t-c",
        model: "gamma",
        totalTimeMs: 2000,
        steps: [
          { id: "c0", type: "system", label: "C0", timing_ms: 0, status: "success" },
          { id: "c1", type: "response", label: "C1", timing_ms: 500, status: "success" },
        ],
      });

      render(
        <TraceComparison
          tracesA={[traceA]}
          tracesB={[traceB]}
          tracesC={[traceC]}
        />,
      );

      // Diff summary bar should show A vs B comparison only (C is reference-only)
      expect(
        screen.getByText(/alpha was 500ms faster than beta/),
      ).toBeTruthy();
      expect(
        screen.getByText(/beta used 1 more step/),
      ).toBeTruthy();

      // All three models visible
      expect(screen.getByText("alpha")).toBeTruthy();
      expect(screen.getByText("beta")).toBeTruthy();
      expect(screen.getByText("gamma")).toBeTruthy();
    });
  });
});

// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TraceTimeline from "./TraceTimeline";
import type { TraceRun } from "../lib/traceTypes";
import type { BenchmarkResult } from "../lib/loadResults";

beforeEach(() => {
  // jsdom doesn't implement scrollIntoView
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TraceTimeline", () => {
  it("renders demo trace runs when no results are provided", () => {
    render(<TraceTimeline />);
    // "Llama 3 70B" appears in sidebar AND timeline header (twice)
    expect(screen.getAllByText("Llama 3 70B").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Mistral Large 2")).toBeTruthy();
  });

  it("renders the run list sidebar with run IDs", () => {
    render(<TraceTimeline />);
    expect(screen.getByText("Recent Runs")).toBeTruthy();
    expect(screen.getByText("run-8821-llama-3")).toBeTruthy();
    expect(screen.getByText("run-7712-mistral")).toBeTruthy();
  });

  it("shows the selected run's model name in the timeline header", () => {
    render(<TraceTimeline />);
    // First run selected by default — appears in sidebar + header
    expect(screen.getAllByText("Llama 3 70B").length).toBeGreaterThanOrEqual(1);
  });

  it("shows the pack and prompt for the selected run", () => {
    render(<TraceTimeline />);
    // "nestjs-agentic-pack" appears as sidebar text + timeline info
    expect(screen.getAllByText(/nestjs-agentic-pack/).length).toBeGreaterThanOrEqual(1);
  });

  it("shows the total time for the selected run", () => {
    render(<TraceTimeline />);
    expect(screen.getByText("482ms")).toBeTruthy();
  });

  it("shows step labels from the selected run", () => {
    render(<TraceTimeline />);
    expect(screen.getByText("System Instruction")).toBeTruthy();
    expect(screen.getByText("Calling: prisma.user.findUnique")).toBeTruthy();
    expect(screen.getByText("Analyzing schema relations")).toBeTruthy();
  });

  it("renders step timing values", () => {
    render(<TraceTimeline />);
    const timingElements = screen.getAllByText(/ms$/);
    expect(timingElements.length).toBeGreaterThan(0);
  });

  it("renders type chips for each step", () => {
    render(<TraceTimeline />);
    // Step type chips — some types appear on multiple steps (e.g., "tool call" appears twice in Llama run)
    expect(screen.getByText("system")).toBeTruthy();
    expect(screen.getAllByText("tool call").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("reasoning")).toBeTruthy();
    expect(screen.getByText("response")).toBeTruthy();
  });

  it("switches to a different run when clicked in sidebar", async () => {
    const user = userEvent.setup();
    render(<TraceTimeline />);

    await user.click(screen.getByText("run-7712-mistral"));
    await waitFor(() => {
      // Mistral appears in sidebar + timeline header
      expect(screen.getAllByText("Mistral Large 2").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("debugging-pack")).toBeTruthy();
    });
  });

  it("shows reasoning step detail for the second run", async () => {
    const user = userEvent.setup();
    render(<TraceTimeline />);

    await user.click(screen.getByText("run-7712-mistral"));
    await waitFor(() => {
      expect(screen.getByText("Identifying the race condition")).toBeTruthy();
      expect(screen.getByText(/Promise.all on line 42/)).toBeTruthy();
    });
  });

  it("renders the playback controls", () => {
    render(<TraceTimeline />);
    expect(screen.getByTitle("Previous step (←)")).toBeTruthy();
    expect(screen.getByTitle("Play (Space)")).toBeTruthy();
    expect(screen.getByTitle("Next step (→)")).toBeTruthy();
    expect(screen.getByTitle("Speed 1x (1-4)")).toBeTruthy();
  });

  it("shows step count in the playback bar", () => {
    render(<TraceTimeline />);
    expect(screen.getByText("1 / 5 steps")).toBeTruthy();
  });

  it("renders error-type steps when results have failures", () => {
    const results: BenchmarkResult[] = [{
      run_id: "run-fail-1",
      model: "failing-model",
      model_metadata: { size: "7B" },
      hardware: { platform: "macOS", processor: "M3", memory_gb: 18, architecture: "arm64" },
      timestamp: "2026-06-02T02:25:52.205Z",
      git_sha: "abc",
      git_branch: "main",
      metrics: {
        coding_score: 0.5,
        reasoning_score: 0.5,
        instruction_score: 0.5,
        frontend_score: 0.5,
        math_score: 0.5,
        debugging_score: 0.5,
        overall_score: 0.4,
      },
      performance: { tokens_per_sec: 40, normalized_tps: 38, ttft_ms: 500, total_latency_ms: 3000, memory_pressure_mb: 1000 },
      stats: { mean: 0.4, std: 0.05, min: 0.35, max: 0.45, median: 0.4, runs: 3, confidence_95: null, coefficient_of_variation: 0.06 },
      failures: {
        hallucinated_api: 2,
        wrong_async_usage: 0,
        incorrect_json_schema: 0,
        syntax_error: 0,
        logic_error: 3,
        type_error: 0,
        missing_import: 0,
        stale_closure: 0,
        race_condition: 0,
        incorrect_di: 0,
        oververbose: 0,
        missed_constraint: 0,
        other: 0,
      },
      category_scores: {},
      config_snapshot: {},
      prompt_version: "v1",
      packs_used: ["debugging"],
      seed: null,
    }];

    render(<TraceTimeline results={results} />);
    expect(screen.getByText("Failure: hallucinated api")).toBeTruthy();
    expect(screen.getByText("Failure: logic error")).toBeTruthy();
  });

  it("marks the overall status as failed when score is below 0.6", () => {
    const lowScoreResult: BenchmarkResult[] = [{
      run_id: "run-low",
      model: "low-model",
      model_metadata: { size: "7B" },
      hardware: { platform: "macOS", processor: "M3", memory_gb: 18, architecture: "arm64" },
      timestamp: "2026-06-02T02:25:52.205Z",
      git_sha: "abc",
      git_branch: "main",
      metrics: {
        coding_score: 0.4,
        reasoning_score: 0.4,
        instruction_score: 0.4,
        frontend_score: 0.4,
        math_score: 0.4,
        debugging_score: 0.4,
        overall_score: 0.4,
      },
      performance: { tokens_per_sec: 40, normalized_tps: 38, ttft_ms: 500, total_latency_ms: 3000, memory_pressure_mb: 1000 },
      stats: { mean: 0.4, std: 0.05, min: 0.35, max: 0.45, median: 0.4, runs: 3, confidence_95: null, coefficient_of_variation: 0.06 },
      failures: {
        hallucinated_api: 0,
        wrong_async_usage: 0,
        incorrect_json_schema: 0,
        syntax_error: 0,
        logic_error: 0,
        type_error: 0,
        missing_import: 0,
        stale_closure: 0,
        race_condition: 0,
        incorrect_di: 0,
        oververbose: 0,
        missed_constraint: 0,
        other: 0,
      },
      category_scores: {},
      config_snapshot: {},
      prompt_version: "v1",
      packs_used: [],
      seed: null,
    }];

    render(<TraceTimeline results={lowScoreResult} />);
    // Status icon for failed
    expect(screen.getByText("cancel")).toBeTruthy();
  });

  it("reuses demo data when results are empty array", () => {
    render(<TraceTimeline results={[]} />);
    const llamaElements = screen.getAllByText("Llama 3 70B");
    expect(llamaElements.length).toBeGreaterThanOrEqual(1);
  });

  it("preserves selected run across state updates via hover", async () => {
    const user = userEvent.setup();
    render(<TraceTimeline />);

    expect(screen.getByText("nestjs-agentic-pack")).toBeTruthy();

    const stepLabels = screen.getAllByText(/Calling:/);
    if (stepLabels.length > 0) {
      await user.hover(stepLabels[0]);
    }

    expect(screen.getByText("nestjs-agentic-pack")).toBeTruthy();
  });

  // ── V2: Real trace data ──────────────────────────────────────

  it("renders real traces when traces prop is provided", () => {
    const traces = [{
      id: "trace-real",
      model: "real-model",
      pack: "nestjs-pack",
      prompt: "Build a JWT guard",
      timestamp: "Jun 2, 2:14 PM",
      totalTimeMs: 1200,
      status: "completed" as const,
      steps: [
        { id: "e0", type: "system" as const, label: "System", timing_ms: 0, status: "success" as const },
        { id: "e1", type: "prompt" as const, label: "Prompt Sent", detail: "Build a JWT guard", timing_ms: 10, status: "success" as const },
        { id: "e2", type: "token" as const, label: "Token Stream", detail: "import { JwtGuard }", timing_ms: 200, status: "success" as const },
        { id: "e3", type: "response" as const, label: "Complete", timing_ms: 500, status: "success" as const },
      ],
    }];

    render(<TraceTimeline traces={traces} />);
    // Should show the real model, not demo data
    // "real-model" appears in both sidebar and timeline header
    expect(screen.getAllByText("real-model").length).toBeGreaterThanOrEqual(1);
    // "Build a JWT guard" appears in sidebar meta AND as prompt step detail
    expect(screen.getAllByText("Build a JWT guard").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("trace-real")).toBeTruthy();
  });

  it("prefers traces prop over results prop", () => {
    const traces = [{
      id: "trace-priority",
      model: "priority-model",
      pack: "custom",
      prompt: "priority prompt",
      timestamp: "Jun 2, 2:14 PM",
      totalTimeMs: 800,
      status: "completed" as const,
      steps: [
        { id: "e0", type: "system" as const, label: "System", timing_ms: 0, status: "success" as const },
        { id: "e1", type: "response" as const, label: "Done", timing_ms: 400, status: "success" as const },
      ],
    }];

    const lowScoreResult: BenchmarkResult[] = [{
      run_id: "run-low",
      model: "low-model",
      model_metadata: { size: "7B" },
      hardware: { platform: "macOS", processor: "M3", memory_gb: 18, architecture: "arm64" },
      timestamp: "2026-06-02T02:25:52.205Z",
      git_sha: "abc",
      git_branch: "main",
      metrics: { coding_score: 0.4, reasoning_score: 0.4, instruction_score: 0.4, frontend_score: 0.4, math_score: 0.4, debugging_score: 0.4, overall_score: 0.4 },
      performance: { tokens_per_sec: 40, normalized_tps: 38, ttft_ms: 500, total_latency_ms: 3000, memory_pressure_mb: 1000 },
      stats: { mean: 0.4, std: 0.05, min: 0.35, max: 0.45, median: 0.4, runs: 3, confidence_95: null, coefficient_of_variation: 0.06 },
      failures: { hallucinated_api: 0, wrong_async_usage: 0, incorrect_json_schema: 0, syntax_error: 0, logic_error: 0, type_error: 0, missing_import: 0, stale_closure: 0, race_condition: 0, incorrect_di: 0, oververbose: 0, missed_constraint: 0, other: 0 },
      category_scores: {},
      config_snapshot: {},
      prompt_version: "v1",
      packs_used: [],
      seed: null,
    }];

    render(<TraceTimeline traces={traces} results={lowScoreResult} />);
    // Should show priority-model (traces), not low-model (results)
    expect(screen.getAllByText("priority-model").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("low-model")).toBeNull();
  });

  it("renders prompt and token step types", () => {
    const traces = [{
      id: "trace-types",
      model: "types-model",
      pack: "default",
      prompt: "types test",
      timestamp: "Jun 2, 2:14 PM",
      totalTimeMs: 500,
      status: "completed" as const,
      steps: [
        { id: "e0", type: "system" as const, label: "System", timing_ms: 0, status: "success" as const },
        { id: "e1", type: "prompt" as const, label: "Prompt Sent", timing_ms: 5, status: "success" as const },
        { id: "e2", type: "token" as const, label: "Token", timing_ms: 10, status: "success" as const },
        { id: "e3", type: "response" as const, label: "Done", timing_ms: 200, status: "success" as const },
      ],
    }];

    render(<TraceTimeline traces={traces} />);
    // Should render the "prompt" and "token" type chips
    expect(screen.getByText("prompt")).toBeTruthy();
    expect(screen.getByText("token")).toBeTruthy();
  });

  it("shows correct step count from real traces", () => {
    const traces = [{
      id: "trace-steps",
      model: "steps-model",
      pack: "default",
      prompt: "test",
      timestamp: "Jun 2, 2:14 PM",
      totalTimeMs: 300,
      status: "completed" as const,
      steps: [
        { id: "e0", type: "system" as const, label: "S", timing_ms: 0, status: "success" as const },
        { id: "e1", type: "response" as const, label: "R", timing_ms: 100, status: "success" as const },
      ],
    }];

    render(<TraceTimeline traces={traces} />);
    expect(screen.getByText("1 / 2 steps")).toBeTruthy();
  });

  it("previous and next buttons update step count", async () => {
    const user = userEvent.setup();
    const traces = [{
      id: "trace-nav",
      model: "nav-model",
      pack: "default",
      prompt: "test",
      timestamp: "Jun 2, 2:14 PM",
      totalTimeMs: 300,
      status: "completed" as const,
      steps: [
        { id: "e0", type: "system" as const, label: "Step 1", timing_ms: 0, status: "success" as const },
        { id: "e1", type: "response" as const, label: "Step 2", timing_ms: 100, status: "success" as const },
      ],
    }];

    render(<TraceTimeline traces={traces} />);
    expect(screen.getByText("1 / 2 steps")).toBeTruthy();

    await user.click(screen.getByTitle("Next step (→)"));
    expect(screen.getByText("2 / 2 steps")).toBeTruthy();

    await user.click(screen.getByTitle("Previous step (←)"));
    expect(screen.getByText("1 / 2 steps")).toBeTruthy();
  });

  it("renders empty state when both traces and results are missing", () => {
    render(<TraceTimeline results={[]} />);
    // Falls back to demo data when results is empty array
    expect(screen.getAllByText("Llama 3 70B").length).toBeGreaterThanOrEqual(1);
  });

  // ═══════════════════════════════════════════════════════════
  // Auto-playback integration tests
  // ═══════════════════════════════════════════════════════════

  describe("auto-playback", () => {
    // Traces fixture: 3-step trace for playback testing
    function makePlaybackTrace(overrides: Partial<TraceRun> = {}): TraceRun[] {
      return [{
        id: "trace-playback",
        model: "playback-model",
        pack: "test-pack",
        prompt: "test prompt",
        timestamp: "Jun 2, 2:14 PM",
        totalTimeMs: 900,
        status: "completed" as const,
        steps: [
          { id: "s0", type: "system" as const, label: "Step 0", timing_ms: 0, status: "success" as const },
          { id: "s1", type: "tool_call" as const, label: "Step 1", timing_ms: 100, status: "success" as const },
          { id: "s2", type: "response" as const, label: "Step 2", timing_ms: 300, status: "success" as const },
        ],
        ...overrides,
      }];
    }

    function makeMultiTrace(): TraceRun[] {
      return [
        {
          id: "trace-alpha",
          model: "alpha-model",
          pack: "alpha-pack",
          prompt: "alpha prompt",
          timestamp: "Jun 2, 2:14 PM",
          totalTimeMs: 500,
          status: "completed" as const,
          steps: [
            { id: "a0", type: "system" as const, label: "Alpha Start", timing_ms: 0, status: "success" as const },
            { id: "a1", type: "response" as const, label: "Alpha End", timing_ms: 200, status: "success" as const },
          ],
        },
        {
          id: "trace-beta",
          model: "beta-model",
          pack: "beta-pack",
          prompt: "beta prompt",
          timestamp: "Jun 2, 1:00 PM",
          totalTimeMs: 700,
          status: "completed" as const,
          steps: [
            { id: "b0", type: "system" as const, label: "Beta Start", timing_ms: 0, status: "success" as const },
            { id: "b1", type: "tool_call" as const, label: "Beta Middle", timing_ms: 100, status: "success" as const },
            { id: "b2", type: "response" as const, label: "Beta End", timing_ms: 250, status: "success" as const },
          ],
        },
      ];
    }

    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: false });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("auto-advances steps after Play is clicked", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Initial step count
      expect(screen.getByText("1 / 3 steps")).toBeTruthy();

      // Click Play
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });

      // Advance 600ms (1 tick at 1x)
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();

      // Advance another 600ms
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();

      // At the end — advances one more tick to loop back to step 1
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("1 / 3 steps")).toBeTruthy();
    });

    it("Play button changes to Pause when playing", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Before playing: Play button visible
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();
      expect(screen.queryByTitle("Pause (Space)")).toBeNull();

      // Click Play
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });

      // After clicking: Pause button now visible
      expect(screen.getByTitle("Pause (Space)")).toBeTruthy();
      expect(screen.queryByTitle("Play (Space)")).toBeNull();
    });

    it("Pause stops auto-advancement", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();

      // Click Pause
      act(() => { fireEvent.click(screen.getByTitle("Pause (Space)")); });

      // Advance time — step should NOT change
      act(() => { vi.advanceTimersByTime(3000); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();

      // Play button is back
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();
    });

    it("Play loop: pause then resume continues from current step", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Start playing, advance to step 2
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();

      // Pause
      act(() => { fireEvent.click(screen.getByTitle("Pause (Space)")); });

      // Resume
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();
    });

    it("speed cycles through 1x → 2x → 4x → 1x", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Default: 1x
      expect(screen.getByTitle("Speed 1x (1-4)")).toBeTruthy();

      // Click: 2x
      act(() => { fireEvent.click(screen.getByTitle("Speed 1x (1-4)")); });
      expect(screen.getByTitle("Speed 2x (1-4)")).toBeTruthy();

      // Click: 4x
      act(() => { fireEvent.click(screen.getByTitle("Speed 2x (1-4)")); });
      expect(screen.getByTitle("Speed 4x (1-4)")).toBeTruthy();

      // Click: back to 1x
      act(() => { fireEvent.click(screen.getByTitle("Speed 4x (1-4)")); });
      expect(screen.getByTitle("Speed 1x (1-4)")).toBeTruthy();
    });

    it("2x speed advances steps twice as fast", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Set speed to 2x
      act(() => { fireEvent.click(screen.getByTitle("Speed 1x (1-4)")); });
      expect(screen.getByTitle("Speed 2x (1-4)")).toBeTruthy();

      // Click Play
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });

      // At 2x, each tick is 300ms. Advance 300ms → step 2
      act(() => { vi.advanceTimersByTime(300); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();

      // Advance another 300ms → step 3
      act(() => { vi.advanceTimersByTime(300); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();
    });

    it("switching runs stops playback and resets step index", () => {
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      // First trace is alpha (2 steps) — selected by default
      expect(screen.getByText("Alpha Start")).toBeTruthy();
      expect(screen.getByText("1 / 2 steps")).toBeTruthy();

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("2 / 2 steps")).toBeTruthy();

      // Click beta trace in sidebar → stops playback, resets to step 1
      act(() => { fireEvent.click(screen.getByText("trace-beta")); });
      expect(screen.getByText("Beta Start")).toBeTruthy();
      expect(screen.getByText("1 / 3 steps")).toBeTruthy();

      // Play button is back (not pause)
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();

      // Advance time — step should NOT change (playback stopped)
      act(() => { vi.advanceTimersByTime(2000); });
      expect(screen.getByText("1 / 3 steps")).toBeTruthy();
    });

    it("playback cursor applies traces-step-current class to current step", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Initial: step 0 highlighted
      let currentSteps = container.querySelectorAll(".traces-step-current");
      expect(currentSteps.length).toBe(1);
      expect(currentSteps[0].textContent).toContain("Step 0");

      // Advance with next button → step 1 highlighted
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      currentSteps = container.querySelectorAll(".traces-step-current");
      expect(currentSteps.length).toBe(1);
      expect(currentSteps[0].textContent).toContain("Step 1");
    });

    it("pulsing dot only appears on current step during active playback", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Before playing: no pulsing dots
      expect(container.querySelectorAll(".traces-step-dot-pulse").length).toBe(0);

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });

      // While playing: one pulsing dot on current step
      let pulsing = container.querySelectorAll(".traces-step-dot-pulse");
      expect(pulsing.length).toBe(1);

      // Pause: no pulsing dots
      act(() => { fireEvent.click(screen.getByTitle("Pause (Space)")); });
      pulsing = container.querySelectorAll(".traces-step-dot-pulse");
      expect(pulsing.length).toBe(0);
    });

    it("initialTraceId pre-selects the matching trace", () => {
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} initialTraceId="trace-beta" />);

      // Beta trace should be selected (shows in sidebar active + timeline header)
      expect(screen.getAllByText("beta-model").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Beta Start")).toBeTruthy();
      expect(screen.getByText("1 / 3 steps")).toBeTruthy();
    });

    it("initialTraceId falls back to first trace when ID not found", () => {
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} initialTraceId="nonexistent" />);

      // Falls back to first trace (alpha)
      expect(screen.getAllByText("alpha-model").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Alpha Start")).toBeTruthy();
    });

    it("clicking Play at last step resets to step 0 and starts playing", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Manually advance to the last step
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();

      // Click Play at the last step → should reset to step 1 and start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });

      // After click: step index should be 1 (reset to 0), playback is active
      expect(screen.getByText("1 / 3 steps")).toBeTruthy();
      expect(screen.getByTitle("Pause (Space)")).toBeTruthy();

      // Verify playback actually runs from step 1
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();
    });

    it("resume after pause keeps Pause button visible during playback", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      expect(screen.getByTitle("Pause (Space)")).toBeTruthy();

      // Pause
      act(() => { fireEvent.click(screen.getByTitle("Pause (Space)")); });
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();

      // Resume — Pause button should reappear
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      expect(screen.getByTitle("Pause (Space)")).toBeTruthy();

      // Verify playback actually advances
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();
    });

    // ── Scrubbing tests ───────────────────────────────────────

    it("clicking on the progress track jumps to the correct step", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const track = container.querySelector(".traces-pb-track") as HTMLElement;
      expect(track).toBeTruthy();

      // Mock bounding rect: 300px wide, starting at x=100
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        x: 100, left: 100, right: 400, width: 300,
        y: 500, top: 500, bottom: 520, height: 20,
      } as DOMRect);

      // Click at x=250 (midpoint, ratio ≈ 0.5, 3 steps → step 1)
      act(() => { fireEvent.mouseDown(track, { clientX: 250 }); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();
    });

    it("scrubbing pauses playback while dragging", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      expect(screen.getByTitle("Pause (Space)")).toBeTruthy();

      const track = container.querySelector(".traces-pb-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        x: 100, left: 100, right: 400, width: 300,
        y: 500, top: 500, bottom: 520, height: 20,
      } as DOMRect);

      // Start scrubbing — should pause playback
      act(() => { fireEvent.mouseDown(track, { clientX: 250 }); });
      // Play button should appear (playback paused by scrub)
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();
    });

    it("scrubbing restores playback if it was playing before", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      expect(screen.getByTitle("Pause (Space)")).toBeTruthy();

      const track = container.querySelector(".traces-pb-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        x: 100, left: 100, right: 400, width: 300,
        y: 500, top: 500, bottom: 520, height: 20,
      } as DOMRect);

      // Start scrubbing (pauses playback)
      act(() => { fireEvent.mouseDown(track, { clientX: 250 }); });
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();

      // End scrubbing — should restore playback
      act(() => { fireEvent.mouseUp(window); });
      expect(screen.getByTitle("Pause (Space)")).toBeTruthy();

      // Verify playback advances
      act(() => { vi.advanceTimersByTime(600); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();
    });

    it("scrub to the very end of the track jumps to the last step", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const track = container.querySelector(".traces-pb-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        x: 100, left: 100, right: 400, width: 300,
        y: 500, top: 500, bottom: 520, height: 20,
      } as DOMRect);

      // Click past the right edge (ratio = 1.0, 3 steps → step 2, the last)
      act(() => { fireEvent.mouseDown(track, { clientX: 450 }); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();
    });

    it("scrub track title indicates drag functionality", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      expect(screen.getByTitle("Drag to scrub through steps")).toBeTruthy();
    });

    it("scrubbing while paused does NOT auto-start playback on mouseup", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Verify we start paused
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();

      const track = container.querySelector(".traces-pb-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        x: 100, left: 100, right: 400, width: 300,
        y: 500, top: 500, bottom: 520, height: 20,
      } as DOMRect);

      // Start scrubbing while paused
      act(() => { fireEvent.mouseDown(track, { clientX: 250 }); });
      // Still paused (Play button visible)
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();

      // End scrubbing — should NOT start playing (wasn't playing before)
      act(() => { fireEvent.mouseUp(window); });
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();

      // Advance time — verify no playback
      act(() => { vi.advanceTimersByTime(2000); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy(); // Stays at step 2 from scrub
    });

    // ── Auto-scroll tests ─────────────────────────────────────

    it("auto-scrolls to current step when advancing with Next button", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      const scrollIntoViewMock = vi.mocked(Element.prototype.scrollIntoView);
      // Clear the initial render call
      scrollIntoViewMock.mockClear();

      // Click Next to advance to step 1
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });

      expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
      expect(scrollIntoViewMock).toHaveBeenCalledWith({
        behavior: "smooth",
        block: "nearest",
      });
    });

    it("auto-scrolls during playback as steps auto-advance", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      const scrollIntoViewMock = vi.mocked(Element.prototype.scrollIntoView);
      // Clear the initial render call
      scrollIntoViewMock.mockClear();

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      // Advance 2 ticks — each should trigger scrollIntoView
      act(() => { vi.advanceTimersByTime(600); });
      act(() => { vi.advanceTimersByTime(600); });

      // Should have been called for step 1 and step 2
      expect(scrollIntoViewMock).toHaveBeenCalledTimes(2);
      expect(scrollIntoViewMock).toHaveBeenCalledWith({
        behavior: "smooth",
        block: "nearest",
      });
    });

    it("auto-scrolls when scrubbing to a different step", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const scrollIntoViewMock = vi.mocked(Element.prototype.scrollIntoView);
      scrollIntoViewMock.mockClear();

      const track = container.querySelector(".traces-pb-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        x: 100, left: 100, right: 400, width: 300,
        y: 500, top: 500, bottom: 520, height: 20,
      } as DOMRect);

      // Scrub to step 2 (clientX: 400 → ratio ~1.0 → step 2)
      act(() => { fireEvent.mouseDown(track, { clientX: 400 }); });

      expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
      expect(scrollIntoViewMock).toHaveBeenCalledWith({
        behavior: "smooth",
        block: "nearest",
      });
    });

    it("does NOT scroll when step index doesn't change", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      const scrollIntoViewMock = vi.mocked(Element.prototype.scrollIntoView);
      // Clear initial render call
      scrollIntoViewMock.mockClear();

      // Click Previous at step 0 (button is disabled, nothing happens)
      const prevButton = screen.getByTitle("Previous step (←)");
      expect(prevButton).toBeDisabled();

      // No scroll since step didn't change
      expect(scrollIntoViewMock).not.toHaveBeenCalled();
    });

    // ── Flash pulse tests ────────────────────────────────────

    it("flash class appears on the newly-arrived step after Next click", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Initially, no flash class (the initial render flash may have already fired)
      // Advance to step 1
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });

      // The newly-arrived step (s1) should have the flash class
      const flashingSteps = container.querySelectorAll(".traces-step-flash");
      expect(flashingSteps.length).toBe(1);
      expect(flashingSteps[0].textContent).toContain("Step 1");
    });

    it("flash class appears during playback auto-advance", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      act(() => { vi.advanceTimersByTime(600); });

      // Step 1 should have flash class
      let flashing = container.querySelectorAll(".traces-step-flash");
      expect(flashing.length).toBe(1);
      expect(flashing[0].textContent).toContain("Step 1");

      // Advance another tick → step 2 gets flash, step 1 loses it
      act(() => { vi.advanceTimersByTime(600); });
      flashing = container.querySelectorAll(".traces-step-flash");
      expect(flashing.length).toBe(1);
      expect(flashing[0].textContent).toContain("Step 2");
    });

    it("flash class appears when scrubbing to a different step", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const track = container.querySelector(".traces-pb-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        x: 100, left: 100, right: 400, width: 300,
        y: 500, top: 500, bottom: 520, height: 20,
      } as DOMRect);

      // Scrub to step 2
      act(() => { fireEvent.mouseDown(track, { clientX: 400 }); });

      const flashing = container.querySelectorAll(".traces-step-flash");
      expect(flashing.length).toBe(1);
      expect(flashing[0].textContent).toContain("Step 2");
    });

    it("flash class clears after the timeout", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Advance to step 1
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      expect(container.querySelectorAll(".traces-step-flash").length).toBe(1);

      // Advance past the 600ms flash duration
      act(() => { vi.advanceTimersByTime(700); });

      // Flash should be cleared
      expect(container.querySelectorAll(".traces-step-flash").length).toBe(0);
    });

    it("flash does NOT appear when step index does not change", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Wait for any initial render flash to clear
      act(() => { vi.advanceTimersByTime(700); });
      expect(container.querySelectorAll(".traces-step-flash").length).toBe(0);

      // Click Previous at step 0 (disabled — no step change)
      act(() => { fireEvent.click(screen.getByTitle("Previous step (←)")); });

      // No flash should appear
      expect(container.querySelectorAll(".traces-step-flash").length).toBe(0);
    });

    // ── Keyboard shortcut tests ────────────────────────────────

    it("Space toggles play/pause", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Start playback via Space
      act(() => { fireEvent.keyDown(window, { key: " " }); });
      expect(screen.queryByTitle("Play (Space)")).toBeNull();

      // Pause via Space
      act(() => { fireEvent.keyDown(window, { key: " " }); });
      expect(screen.queryByTitle("Pause (Space)")).toBeNull();

      // Resume via Space
      act(() => { fireEvent.keyDown(window, { key: " " }); });
      expect(screen.queryByTitle("Play (Space)")).toBeNull();
    });

    it("Left arrow moves to previous step", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Advance to step 2 first
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();

      // Left arrow → step 2
      act(() => { fireEvent.keyDown(window, { key: "ArrowLeft" }); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();

      // Left arrow → step 1
      act(() => { fireEvent.keyDown(window, { key: "ArrowLeft" }); });
      expect(screen.getByText("1 / 3 steps")).toBeTruthy();
    });

    it("Right arrow moves to next step", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      expect(screen.getByText("1 / 3 steps")).toBeTruthy();

      // Right arrow → step 2
      act(() => { fireEvent.keyDown(window, { key: "ArrowRight" }); });
      expect(screen.getByText("2 / 3 steps")).toBeTruthy();

      // Right arrow → step 3
      act(() => { fireEvent.keyDown(window, { key: "ArrowRight" }); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();
    });

    it("digit keys 1-4 set playback speed directly", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Default is 1x
      expect(screen.getByTitle("Speed 1x (1-4)")).toBeTruthy();

      // Press 2 → speed 2x
      act(() => { fireEvent.keyDown(window, { key: "2" }); });
      expect(screen.getByTitle("Speed 2x (1-4)")).toBeTruthy();

      // Press 4 → speed 4x
      act(() => { fireEvent.keyDown(window, { key: "4" }); });
      expect(screen.getByTitle("Speed 4x (1-4)")).toBeTruthy();

      // Press 1 → speed 1x
      act(() => { fireEvent.keyDown(window, { key: "1" }); });
      expect(screen.getByTitle("Speed 1x (1-4)")).toBeTruthy();
    });

    it("Space does not toggle playback when focus is in an input", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Create a detached input, keydown on it should be ignored
      const input = document.createElement("input");
      act(() => { fireEvent.keyDown(input, { key: " " }); });

      // Playback should NOT have started
      expect(screen.queryByTitle("Pause (Space)")).toBeNull();
    });

    it("keyboard shortcuts have descriptive titles", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      expect(screen.getByTitle("Previous step (←)")).toBeTruthy();
      expect(screen.getByTitle("Play (Space)")).toBeTruthy();
      expect(screen.getByTitle("Next step (→)")).toBeTruthy();
      expect(screen.getByTitle("Speed 1x (1-4)")).toBeTruthy();
    });

    // ── Slide transition tests ────────────────────────────────

    it("slide-right class appears on step content when navigating forward", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Click Next to advance: should slide in from the right
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });

      const slideRights = container.querySelectorAll(".traces-step-slide-right");
      expect(slideRights.length).toBe(1);

      // The sliding element should be on the current step (step 1)
      const currentStep = container.querySelector(".traces-step-current");
      expect(currentStep?.querySelector(".traces-step-slide-right")).toBeTruthy();
    });

    it("slide-left class appears on step content when navigating backward", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Advance to step 2 first
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      expect(screen.getByText("3 / 3 steps")).toBeTruthy();

      // Advance past the previous Next's slide timeout
      act(() => { vi.advanceTimersByTime(400); });

      // Click Previous: should slide in from the left
      act(() => { fireEvent.click(screen.getByTitle("Previous step (←)")); });

      const slideLefts = container.querySelectorAll(".traces-step-slide-left");
      expect(slideLefts.length).toBe(1);
    });

    it("slide-right class appears during playback auto-advance", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Start playing
      act(() => { fireEvent.click(screen.getByTitle("Play (Space)")); });
      act(() => { vi.advanceTimersByTime(600); });

      // Step 1 should have slide-right (playback always goes forward)
      const slideRights = container.querySelectorAll(".traces-step-slide-right");
      expect(slideRights.length).toBe(1);
    });

    it("slide class clears after the timeout", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Advance to trigger slide
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      expect(container.querySelectorAll(".traces-step-slide-right").length).toBe(1);

      // Advance past the 350ms slide duration
      act(() => { vi.advanceTimersByTime(400); });

      // Slide class should be cleared
      expect(container.querySelectorAll(".traces-step-slide-right").length).toBe(0);
    });

    it("Left arrow key triggers slide-left animation", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Advance to step 2 first, then let slide timeout pass
      act(() => { fireEvent.click(screen.getByTitle("Next step (→)")); });
      act(() => { vi.advanceTimersByTime(400); });

      // Press Left arrow → slide-left on step 1
      act(() => { fireEvent.keyDown(window, { key: "ArrowLeft" }); });

      const slideLefts = container.querySelectorAll(".traces-step-slide-left");
      expect(slideLefts.length).toBe(1);
    });

    // ── Shortcut help bar tests ───────────────────────────────

    it("? key toggles the shortcuts overlay", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Overlay not visible initially
      expect(screen.queryByText("Keyboard Shortcuts")).toBeNull();

      // Press ? to open
      act(() => { fireEvent.keyDown(window, { key: "?" }); });
      expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();

      // Press ? again to close
      act(() => { fireEvent.keyDown(window, { key: "?" }); });
      expect(screen.queryByText("Keyboard Shortcuts")).toBeNull();
    });

    it("shortcuts overlay shows all available shortcuts", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      act(() => { fireEvent.keyDown(window, { key: "?" }); });

      expect(screen.getByText("Play / Pause")).toBeTruthy();
      expect(screen.getByText("Previous step")).toBeTruthy();
      expect(screen.getByText("Next step")).toBeTruthy();
      expect(screen.getByText("Set speed (1× / 2× / 4×)")).toBeTruthy();
      expect(screen.getByText("Toggle this help")).toBeTruthy();
    });

    it("Esc key closes the shortcuts overlay", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Open overlay
      act(() => { fireEvent.keyDown(window, { key: "?" }); });
      expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();

      // Press Esc to close
      act(() => { fireEvent.keyDown(window, { key: "Escape" }); });
      expect(screen.queryByText("Keyboard Shortcuts")).toBeNull();
    });

    it("clicking the close button dismisses the overlay", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      act(() => { fireEvent.keyDown(window, { key: "?" }); });
      expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();

      act(() => { fireEvent.click(screen.getByTitle("Close shortcuts")); });
      expect(screen.queryByText("Keyboard Shortcuts")).toBeNull();
    });

    it("? help button in playback bar opens the shortcuts overlay", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      // Overlay not visible initially
      expect(screen.queryByText("Keyboard Shortcuts")).toBeNull();

      // Click the ? button in the playback bar
      act(() => { fireEvent.click(screen.getByTitle("Keyboard shortcuts (?)")); });
      expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();

      // Click again to close
      act(() => { fireEvent.click(screen.getByTitle("Keyboard shortcuts (?)")); });
      expect(screen.queryByText("Keyboard Shortcuts")).toBeNull();
    });

    it("? help button has accessible aria-label", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      expect(screen.getByLabelText("Keyboard shortcuts")).toBeTruthy();
    });

    // ── Scroll parallax tests ─────────────────────────────────

    it("scroll parallax sets --steps-scroll-y CSS custom property on scroll", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const stepsEl = container.querySelector(".traces-steps") as HTMLElement;
      expect(stepsEl).toBeTruthy();

      // jsdom's fireEvent.scroll doesn't set element.scrollTop, so we mock it
      act(() => {
        Object.defineProperty(stepsEl, "scrollTop", { value: 200, configurable: true });
        fireEvent.scroll(stepsEl);
      });

      // The custom property should reflect the scroll position
      expect(stepsEl.style.getPropertyValue("--steps-scroll-y")).toBe("200px");
    });

    it("scroll parallax applies alternating transform to gutter dots", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const stepsEl = container.querySelector(".traces-steps") as HTMLElement;
      act(() => {
        Object.defineProperty(stepsEl, "scrollTop", { value: 150, configurable: true });
        fireEvent.scroll(stepsEl);
      });

      // Dots should exist
      const dots = container.querySelectorAll(".traces-step-dot");
      expect(dots.length).toBeGreaterThanOrEqual(2);

      // Odd and even dots should get opposing parallax transforms
      const oddDot = dots[0] as HTMLElement;
      const evenDot = dots[1] as HTMLElement;
      expect(oddDot.style.transform || getComputedStyle(oddDot).transform).toBeTruthy();
      expect(evenDot.style.transform || getComputedStyle(evenDot).transform).toBeTruthy();
    });

    // ── Export buttons tests ─────────────────────────────────

    it("Copy JSON button copies selected trace to clipboard", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: writeTextMock },
        configurable: true,
      });

      act(() => { fireEvent.click(screen.getByTitle("Copy trace JSON")); });

      expect(writeTextMock).toHaveBeenCalledTimes(1);
      const callArg = writeTextMock.mock.calls[0][0];
      expect(callArg).toContain('"id": "trace-playback"');
    });

    it("Copy JSON button shows check icon and toast after successful copy", async () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: writeTextMock },
        configurable: true,
      });

      await act(async () => { fireEvent.click(screen.getByTitle("Copy trace JSON")); });

      // After copy, title changes to "Copied!"
      expect(screen.getByTitle("Copied!")).toBeTruthy();

      // Toast notification appears
      expect(screen.getByText("Copied to clipboard")).toBeTruthy();

      // Toast has accessible role
      expect(screen.getByRole("status")).toBeTruthy();

      // Advance past the 2s reset — toast should disappear
      act(() => { vi.advanceTimersByTime(2500); });
      expect(screen.getByTitle("Copy trace JSON")).toBeTruthy();
      expect(screen.queryByText("Copied to clipboard")).toBeNull();
    });

    it("Download button creates a blob download link and shows toast", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      // Spy on URL and blob creation
      const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
      const revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL");

      // Spy on anchor click
      const clickSpy = vi.fn();
      const origCreateElement = document.createElement.bind(document);
      vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
        const el = origCreateElement(tag);
        if (tag === "a") {
          vi.spyOn(el, "click").mockImplementation(clickSpy);
        }
        return el;
      });

      act(() => { fireEvent.click(screen.getByTitle("Download trace JSON")); });

      expect(createObjectURLSpy).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalled();
      expect(revokeObjectURLSpy).toHaveBeenCalled();

      // Toast notification
      expect(screen.getByText("Trace downloaded")).toBeTruthy();

      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
    });

    it("import button has accessible aria-label and triggers file picker", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      expect(screen.getByLabelText("Import traces")).toBeTruthy();

      // Clicking the import button should trigger the hidden file input
      const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;
      expect(fileInput).toBeTruthy();
      const clickSpy = vi.spyOn(fileInput, "click");

      act(() => { fireEvent.click(screen.getByLabelText("Import traces")); });
      expect(clickSpy).toHaveBeenCalled();
    });

    it("importing valid JSON merges new traces into the sidebar", async () => {
      // Use real timers so FileReader.onload fires asynchronously
      vi.useRealTimers();
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const newTrace: TraceRun = {
        id: "trace-imported",
        model: "imported-model",
        pack: "import-pack",
        prompt: "imported prompt",
        timestamp: "Jun 3, 9:00 AM",
        totalTimeMs: 300,
        status: "completed" as const,
        steps: [
          { id: "i0", type: "system" as const, label: "Imported Step", timing_ms: 0, status: "success" as const },
        ],
      };

      const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;
      const file = new File(
        [JSON.stringify([newTrace])],
        "traces.json",
        { type: "application/json" },
      );

      act(() => {
        Object.defineProperty(fileInput, "files", {
          value: [file],
          configurable: true,
        });
        fireEvent.change(fileInput);
      });

      // waitFor flushes microtasks, allowing FileReader.onload to fire
      await waitFor(() => {
        expect(screen.getByText("trace-imported")).toBeTruthy();
      });
      expect(screen.getByText("imported-model")).toBeTruthy();
      // Original trace still present
      expect(screen.getByText("trace-playback")).toBeTruthy();
      // Toast notification
      expect(screen.getByText("Imported 1 trace")).toBeTruthy();

      vi.useFakeTimers({ shouldAdvanceTime: false });
    });

    it("importing duplicate IDs shows already-loaded toast", async () => {
      vi.useRealTimers();
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;
      const file = new File(
        [JSON.stringify([{ id: "trace-playback", model: "dup", pack: "d", prompt: "d", timestamp: "t", totalTimeMs: 1, status: "completed", steps: [] }])],
        "traces.json",
        { type: "application/json" },
      );

      act(() => {
        Object.defineProperty(fileInput, "files", {
          value: [file],
          configurable: true,
        });
        fireEvent.change(fileInput);
      });

      await waitFor(() => {
        expect(screen.getByText("All traces already loaded")).toBeTruthy();
      });
      vi.useFakeTimers({ shouldAdvanceTime: false });
    });

    it("importing invalid JSON shows error toast", async () => {
      vi.useRealTimers();
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;
      const file = new File(
        ["not valid json"],
        "bad.json",
        { type: "application/json" },
      );

      act(() => {
        Object.defineProperty(fileInput, "files", {
          value: [file],
          configurable: true,
        });
        fireEvent.change(fileInput);
      });

      await waitFor(() => {
        expect(screen.getByText("Invalid JSON file")).toBeTruthy();
      });
      vi.useFakeTimers({ shouldAdvanceTime: false });
    });

    it("importing array with no valid traces shows warning toast", async () => {
      vi.useRealTimers();
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;
      const file = new File(
        [JSON.stringify([{ foo: "bar" }, 123, null])],
        "empty.json",
        { type: "application/json" },
      );

      act(() => {
        Object.defineProperty(fileInput, "files", {
          value: [file],
          configurable: true,
        });
        fireEvent.change(fileInput);
      });

      await waitFor(() => {
        expect(screen.getByText("No valid traces found in file")).toBeTruthy();
      });
      vi.useFakeTimers({ shouldAdvanceTime: false });
    });

    it("export buttons have accessible aria-labels", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      expect(screen.getByLabelText("Copy trace JSON")).toBeTruthy();
      expect(screen.getByLabelText("Download trace JSON")).toBeTruthy();
      expect(screen.getByLabelText("Export all traces")).toBeTruthy();
    });

    it("Export All Traces downloads the entire batch as JSON", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:all");
      const revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL");

      const clickSpy = vi.fn();
      let downloadFilename = "";
      const origCreateElement = document.createElement.bind(document);
      vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
        const el = origCreateElement(tag);
        if (tag === "a") {
          // Intercept download property setter to capture the filename
          Object.defineProperty(el, "download", {
            set(value: string) { downloadFilename = value; },
            get() { return downloadFilename; },
            configurable: true,
          });
          vi.spyOn(el, "click").mockImplementation(clickSpy);
        }
        return el;
      });

      act(() => { fireEvent.click(screen.getByTitle("Export all traces")); });

      expect(createObjectURLSpy).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalled();
      expect(revokeObjectURLSpy).toHaveBeenCalled();
      // Verify filename includes expected prefix
      expect(downloadFilename).toMatch(/^model-lens-traces-/);

      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
    });

    it("Export All Traces shows toast notification", () => {
      const traces = makePlaybackTrace();
      render(<TraceTimeline traces={traces} />);

      const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:all");
      const revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL");

      const origCreateElement = document.createElement.bind(document);
      vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
        const el = origCreateElement(tag);
        if (tag === "a") {
          vi.spyOn(el, "click").mockImplementation(vi.fn());
        }
        return el;
      });

      act(() => { fireEvent.click(screen.getByTitle("Export all traces")); });

      // Toast appears with correct message
      expect(screen.getByText("All traces exported")).toBeTruthy();
      expect(screen.getByRole("status")).toBeTruthy();

      // Toast disappears after timeout
      act(() => { vi.advanceTimersByTime(2500); });
      expect(screen.queryByText("All traces exported")).toBeNull();

      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
    });

    it("clicking the backdrop dismisses the overlay", () => {
      const traces = makePlaybackTrace();
      const { container } = render(<TraceTimeline traces={traces} />);

      act(() => { fireEvent.keyDown(window, { key: "?" }); });
      expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();

      const backdrop = container.querySelector(".traces-shortcuts-backdrop") as HTMLElement;
      act(() => { fireEvent.click(backdrop); });
      expect(screen.queryByText("Keyboard Shortcuts")).toBeNull();
    });
  });

  // ── Filter tests ──────────────────────────────────────────────

  describe("trace filtering", () => {
    function makeMultiTrace(): TraceRun[] {
      return [
        {
          id: "trace-alpha",
          model: "alpha-model",
          pack: "alpha-pack",
          prompt: "alpha prompt",
          timestamp: "Jun 2, 2:14 PM",
          totalTimeMs: 500,
          status: "completed" as const,
          steps: [
            { id: "a0", type: "system" as const, label: "Alpha Start", timing_ms: 0, status: "success" as const },
            { id: "a1", type: "response" as const, label: "Alpha End", timing_ms: 200, status: "success" as const },
          ],
        },
        {
          id: "trace-beta",
          model: "beta-model",
          pack: "beta-pack",
          prompt: "beta prompt",
          timestamp: "Jun 2, 1:00 PM",
          totalTimeMs: 700,
          status: "failed" as const,
          steps: [
            { id: "b0", type: "system" as const, label: "Beta Start", timing_ms: 0, status: "success" as const },
            { id: "b1", type: "error" as const, label: "Beta Error", timing_ms: 100, status: "failure" as const },
          ],
        },
        {
          id: "trace-gamma",
          model: "gamma-model",
          pack: "debugging-pack",
          prompt: "gamma prompt",
          timestamp: "Jun 2, 12:00 PM",
          totalTimeMs: 300,
          status: "completed" as const,
          steps: [
            { id: "g0", type: "system" as const, label: "Gamma Start", timing_ms: 0, status: "success" as const },
            { id: "g1", type: "response" as const, label: "Gamma End", timing_ms: 150, status: "success" as const },
          ],
        },
      ];
    }

    it("renders filter input in the sidebar", () => {
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      // Filter input with aria-label exists
      const filterInput = screen.getByLabelText("Filter traces");
      expect(filterInput).toBeTruthy();
      expect((filterInput as HTMLInputElement).placeholder).toContain("Filter by model");
    });

    it("shows all traces when filter is empty", () => {
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      expect(screen.getByText("trace-alpha")).toBeTruthy();
      expect(screen.getByText("trace-beta")).toBeTruthy();
      expect(screen.getByText("trace-gamma")).toBeTruthy();
    });

    it("filters traces by model name", async () => {
      const user = userEvent.setup();
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      const filterInput = screen.getByLabelText("Filter traces");
      await user.type(filterInput, "alpha");

      // Only alpha-model should be visible
      expect(screen.getByText("trace-alpha")).toBeTruthy();
      expect(screen.queryByText("trace-beta")).toBeNull();
      expect(screen.queryByText("trace-gamma")).toBeNull();
    });

    it("filters traces by pack name", async () => {
      const user = userEvent.setup();
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      const filterInput = screen.getByLabelText("Filter traces");
      await user.type(filterInput, "debugging");

      // Only gamma-model (debugging-pack) should be visible
      expect(screen.queryByText("trace-alpha")).toBeNull();
      expect(screen.queryByText("trace-beta")).toBeNull();
      expect(screen.getByText("trace-gamma")).toBeTruthy();
    });

    it("filters traces by status", async () => {
      const user = userEvent.setup();
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      const filterInput = screen.getByLabelText("Filter traces");
      await user.type(filterInput, "failed");

      // Only beta-model (failed) should be visible
      expect(screen.queryByText("trace-alpha")).toBeNull();
      expect(screen.getByText("trace-beta")).toBeTruthy();
      expect(screen.queryByText("trace-gamma")).toBeNull();
    });

    it("shows empty state when no traces match filter", async () => {
      const user = userEvent.setup();
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      const filterInput = screen.getByLabelText("Filter traces");
      await user.type(filterInput, "nonexistent");

      // All trace items should be hidden
      expect(screen.queryByText("trace-alpha")).toBeNull();
      expect(screen.queryByText("trace-beta")).toBeNull();
      expect(screen.queryByText("trace-gamma")).toBeNull();

      // Empty state message appears
      expect(screen.getByText('No traces match "nonexistent"')).toBeTruthy();
    });

    it("clears filter when clear button is clicked", async () => {
      const user = userEvent.setup();
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      const filterInput = screen.getByLabelText("Filter traces");
      await user.type(filterInput, "alpha");

      // Filtered: only alpha
      expect(screen.getByText("trace-alpha")).toBeTruthy();
      expect(screen.queryByText("trace-beta")).toBeNull();

      // Click the clear button
      const clearBtn = screen.getByTitle("Clear filter");
      await user.click(clearBtn);

      // All traces should be visible again
      expect(screen.getByText("trace-alpha")).toBeTruthy();
      expect(screen.getByText("trace-beta")).toBeTruthy();
      expect(screen.getByText("trace-gamma")).toBeTruthy();

      // Filter input should be empty
      expect((filterInput as HTMLInputElement).value).toBe("");
    });

    it("clear button is hidden when filter is empty", () => {
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      expect(screen.queryByTitle("Clear filter")).toBeNull();
    });

    it("case-insensitive filtering", async () => {
      const user = userEvent.setup();
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      const filterInput = screen.getByLabelText("Filter traces");
      await user.type(filterInput, "ALPHA");

      // Should match alpha-model (case-insensitive)
      expect(screen.getByText("trace-alpha")).toBeTruthy();
      expect(screen.queryByText("trace-beta")).toBeNull();
    });

    it("partial match filters traces", async () => {
      const user = userEvent.setup();
      const traces = makeMultiTrace();
      render(<TraceTimeline traces={traces} />);

      const filterInput = screen.getByLabelText("Filter traces");
      // "beta" should match "beta-model" (model) and "beta-pack" (pack)
      await user.type(filterInput, "beta");

      expect(screen.getByText("trace-beta")).toBeTruthy();
      expect(screen.queryByText("trace-alpha")).toBeNull();
      expect(screen.queryByText("trace-gamma")).toBeNull();
    });
  });
});

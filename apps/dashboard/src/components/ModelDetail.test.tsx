// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ModelDetail from "./ModelDetail";
import type { TraceRun } from "../lib/traceTypes";

const mockResults = [
  {
    run_id: "demo_qwopus3.5-9b-coder",
    model: "qwopus3.5-9b-coder",
    model_metadata: { size: "7B", quantization: "Q4_K_M" },
    hardware: {
      platform: "macOS 15.6.1",
      processor: "Apple M3 Pro",
      memory_gb: 18,
      architecture: "arm64",
    },
    timestamp: "2026-06-02T02:25:52.205Z",
    git_sha: "abc1234",
    git_branch: "main",
    metrics: {
      coding_score: 0.82,
      reasoning_score: 0.78,
      instruction_score: 0.9,
      frontend_score: 0.72,
      math_score: 0.75,
      debugging_score: 0.68,
      overall_score: 0.802,
    },
    performance: {
      tokens_per_sec: 72,
      normalized_tps: 68.4,
      ttft_ms: 420,
      total_latency_ms: 2920,
      memory_pressure_mb: 1200,
    },
    stats: {
      mean: 0.81,
      std: 0.05,
      min: 0.75,
      max: 0.88,
      median: 0.82,
      runs: 5,
      confidence_95: [0.78, 0.85],
      coefficient_of_variation: 0.06,
    },
    failures: {
      hallucinated_api: 3,
      wrong_async_usage: 2,
      incorrect_json_schema: 1,
      syntax_error: 0,
      logic_error: 4,
      type_error: 2,
      missing_import: 1,
      stale_closure: 1,
      race_condition: 2,
      incorrect_di: 0,
      oververbose: 1,
      missed_constraint: 0,
      other: 0,
    },
    category_scores: {},
    config_snapshot: { temperature: 0.2, max_tokens: 1000 },
    prompt_version: "v1",
    packs_used: ["nestjs-pack", "react-pack", "debugging-pack"],
    seed: 42,
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

function makeTraceRun(overrides: Partial<TraceRun> & { id: string }): TraceRun {
  return {
    model: "qwopus3.5-9b-coder",
    pack: "nestjs-pack",
    prompt: "Build a JWT guard for NestJS authentication",
    timestamp: "Jun 2, 2:14 PM",
    totalTimeMs: 1200,
    status: "completed",
    steps: [
      { id: "s0", type: "system", label: "System", timing_ms: 0, status: "success" as const },
      { id: "s1", type: "prompt", label: "Prompt", timing_ms: 5, status: "success" as const },
      { id: "s2", type: "response", label: "Done", timing_ms: 200, status: "success" as const },
    ],
    ...overrides,
  };
}

describe("ModelDetail", () => {
  beforeEach(() => {
    // Prevent redirect when model not found
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
    });
  });

  it("shows loading state initially", () => {
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    expect(screen.getByText("Loading model data...")).toBeTruthy();
  });

  it("renders the model name after loading", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText("qwopus3.5-9b-coder")).toBeTruthy();
    });
  });

  it("renders the overall score percentage", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText(/80.2%/)).toBeTruthy();
    });
  });

  it("renders score breakdown section with all categories", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText("Coding")).toBeTruthy();
      expect(screen.getByText("Reasoning")).toBeTruthy();
      expect(screen.getByText("Instructions")).toBeTruthy();
      expect(screen.getByText("Frontend")).toBeTruthy();
      expect(screen.getByText("Math")).toBeTruthy();
      expect(screen.getByText("Debugging")).toBeTruthy();
    });
  });

  it("renders score percentages for each category", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText("82.0%")).toBeTruthy();
      expect(screen.getByText("78.0%")).toBeTruthy();
      expect(screen.getByText("90.0%")).toBeTruthy();
    });
  });

  it("renders performance section with hardware info", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText(/Apple M3/)).toBeTruthy();
      expect(screen.getByText(/18GB/)).toBeTruthy();
    });
  });

  it("renders tokens per second in performance section", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    const { container } = render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      // Use getAllByText since "72" could also appear as "72.0%" substring match
      const elements = screen.getAllByText("72");
      // At least one element should be the tokens_per_sec value (not a percentage)
      expect(
        elements.some(
          (el) => el.textContent === "72" && !el.textContent?.includes("%"),
        ),
      ).toBe(true);
    });
  });

  it("renders ttft and total latency", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText("420")).toBeTruthy();
      expect(screen.getByText("2920")).toBeTruthy();
    });
  });

  it("renders statistical summary section", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText("Statistical Summary")).toBeTruthy();
      expect(screen.getByText("Mean")).toBeTruthy();
      expect(screen.getByText("Std Dev")).toBeTruthy();
      expect(screen.getByText("Min")).toBeTruthy();
      expect(screen.getByText("Max")).toBeTruthy();
      expect(screen.getByText("Median")).toBeTruthy();
      expect(screen.getByText("CoV")).toBeTruthy();
    });
  });

  it("renders confidence interval", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText(/95% CI/)).toBeTruthy();
      expect(screen.getByText(/0.78/)).toBeTruthy();
      expect(screen.getByText(/0.85/)).toBeTruthy();
    });
  });

  it("renders failure breakdown section", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText("Failure Breakdown")).toBeTruthy();
      expect(screen.getByText(/total/)).toBeTruthy();
    });
  });

  it("renders reproducibility metadata section", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText("Reproducibility")).toBeTruthy();
      expect(screen.getByText("Run ID")).toBeTruthy();
      expect(screen.getByText("Git SHA")).toBeTruthy();
      expect(screen.getByText("Git Branch")).toBeTruthy();
    });
  });

  it("renders run_id and git sha as code elements", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    const { container } = render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      const codeEls = container.querySelectorAll("code");
      const match = Array.from(codeEls).find(
        (el) => el.textContent === "demo_qwopus3.5-9b-coder",
      );
      expect(match).toBeTruthy();
    });
  });

  it("renders model metadata size and quantization", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.getByText(/7B/)).toBeTruthy();
      expect(screen.getByText(/Q4_K_M/)).toBeTruthy();
    });
  });

  it("shows 'Model not found' when modelId doesn't match any result", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="non-existent-model" />);
    await waitFor(() => {
      expect(screen.getByText(/Model not found/)).toBeTruthy();
    });
  });

  // ── Traces section (V2) ────────────────────────────────────

  it("shows 'No execution traces' message when traces array is empty", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" traces={[]} />);
    await waitFor(() => {
      expect(screen.getByText(/No execution traces captured yet/)).toBeTruthy();
    });
  });

  it("does not render traces section when traces prop is undefined", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    render(<ModelDetail modelId="qwopus3.5-9b-coder" />);
    await waitFor(() => {
      expect(screen.queryByText("Recent Execution Traces")).toBeNull();
      expect(screen.queryByText("Execution Traces")).toBeNull();
    });
  });

  it("renders trace cards with correct links for provided traces", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    const traces: TraceRun[] = [
      makeTraceRun({ id: "trace-abc" }),
      makeTraceRun({ id: "trace-def", totalTimeMs: 800, steps: [{ id: "s0", type: "system", label: "Start", timing_ms: 0, status: "success" as const }] }),
    ];

    render(<ModelDetail modelId="qwopus3.5-9b-coder" traces={traces} />);
    await waitFor(() => {
      expect(screen.getByText("Recent Execution Traces")).toBeTruthy();
    });

    // Trace IDs shown
    expect(screen.getByText("trace-abc")).toBeTruthy();
    expect(screen.getByText("trace-def")).toBeTruthy();

    // Trace card links point to the trace explorer
    const links = screen.getAllByRole("link");
    const traceLinks = links.filter((el) =>
      el.getAttribute("href")?.startsWith("/traces?trace_id="),
    );
    expect(traceLinks).toHaveLength(2);
    expect(traceLinks[0].getAttribute("href")).toBe("/traces?trace_id=trace-abc");
    expect(traceLinks[1].getAttribute("href")).toBe("/traces?trace_id=trace-def");
  });

  it("renders trace metadata (steps, timing, pack) in cards", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    const traces: TraceRun[] = [
      makeTraceRun({ id: "trace-xyz", totalTimeMs: 2500, pack: "react-pack" }),
    ];

    render(<ModelDetail modelId="qwopus3.5-9b-coder" traces={traces} />);
    await waitFor(() => {
      expect(screen.getByText("Recent Execution Traces")).toBeTruthy();
    });

    // Metadata
    expect(screen.getByText(/2500ms/)).toBeTruthy();
    expect(screen.getByText(/3 steps/)).toBeTruthy();
    expect(screen.getByText("react-pack")).toBeTruthy();
    // Prompt preview
    expect(screen.getByText(/Build a JWT guard/)).toBeTruthy();
  });

  it("shows truncated prompt for long prompts in trace cards", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    const longPrompt = "A".repeat(200);
    const traces: TraceRun[] = [
      makeTraceRun({ id: "trace-long", prompt: longPrompt }),
    ];

    render(<ModelDetail modelId="qwopus3.5-9b-coder" traces={traces} />);
    await waitFor(() => {
      expect(screen.getByText("Recent Execution Traces")).toBeTruthy();
    });

    // Prompt should be truncated (first 100 chars + ellipsis = 101 visible chars)
    const visiblePrompt = screen.getByText(new RegExp("^A{100}…$"));
    expect(visiblePrompt).toBeTruthy();
  });

  it("shows 'View all traces' link with model filter", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    const traces: TraceRun[] = [makeTraceRun({ id: "trace-1" })];

    render(<ModelDetail modelId="qwopus3.5-9b-coder" traces={traces} />);
    await waitFor(() => {
      expect(screen.getByText("Recent Execution Traces")).toBeTruthy();
    });

    const viewAll = screen.getByText(/View all traces for/);
    expect(viewAll).toBeTruthy();
    const viewAllLink = viewAll.closest("a");
    expect(viewAllLink?.getAttribute("href")).toBe(
      "/traces?model=qwopus3.5-9b-coder",
    );
  });

  it("shows failed status badge for failed traces", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          version: "1",
          generated_at: "",
          total_models: 1,
          total_runs: 1,
          runs: mockResults,
        }),
    });

    const traces: TraceRun[] = [
      makeTraceRun({ id: "trace-fail", status: "failed" }),
    ];

    render(<ModelDetail modelId="qwopus3.5-9b-coder" traces={traces} />);
    await waitFor(() => {
      expect(screen.getByText("Recent Execution Traces")).toBeTruthy();
    });

    // Status badge shows "failed"
    const failedBadges = screen.getAllByText("failed");
    expect(failedBadges.length).toBeGreaterThanOrEqual(1);
  });
});

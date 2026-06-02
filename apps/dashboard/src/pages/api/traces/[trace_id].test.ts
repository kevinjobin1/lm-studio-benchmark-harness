import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock loadTrace for the detail endpoint
const mockLoadTrace = vi.hoisted(() =>
  vi.fn().mockResolvedValue(null),
);

vi.mock("../../../lib/loadTraces", () => ({
  loadTrace: mockLoadTrace,
  loadTraceManifest: vi.fn(),
  loadTraceList: vi.fn(),
}));

const { GET } = await import("./[trace_id]");

describe("GET /api/traces/[trace_id]", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns 400 when trace_id is missing", async () => {
    const response = await GET({
      request: new Request("http://localhost:4321/api/traces/"),
      params: { trace_id: undefined },
    } as any);
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.error).toBe("Missing trace_id");
  });

  it("returns 404 when trace is not found", async () => {
    mockLoadTrace.mockResolvedValue(null);
    const response = await GET({
      request: new Request("http://localhost:4321/api/traces/nonexistent"),
      params: { trace_id: "nonexistent" },
    } as any);
    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.error).toContain("not found");
  });

  it("returns 200 with trace data when found", async () => {
    const fixture = {
      trace_id: "trace-abc",
      run_id: "run-1",
      model: "test-model",
      provider: "test",
      prompt: "hello",
      pack: "",
      timestamp: "2026-06-02T12:00:00Z",
      totalTimeMs: 1500,
      status: "completed" as const,
      steps: [],
      metrics: {
        ttft_ms: 100,
        tokens_per_second: 50,
        total_tokens: 10,
        prompt_tokens: 5,
        completion_tokens: 5,
        total_latency_ms: 1500,
        memory_pressure_mb: 800,
        token_timings_ms: [],
      },
      artifacts: { response: "hi", logs: [], errors: [] },
    };
    mockLoadTrace.mockResolvedValue(fixture);

    const response = await GET({
      request: new Request("http://localhost:4321/api/traces/trace-abc"),
      params: { trace_id: "trace-abc" },
    } as any);
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("application/json");

    const body = await response.json();
    expect(body.trace_id).toBe("trace-abc");
    expect(body.model).toBe("test-model");
  });

  it("URI-decodes the trace_id param", async () => {
    mockLoadTrace.mockResolvedValue(null);
    const response = await GET({
      request: new Request("http://localhost:4321/api/traces/trace%20with%20spaces"),
      params: { trace_id: "trace%20with%20spaces" },
    } as any);
    // Should pass decoded value to loadTrace
    expect(mockLoadTrace).toHaveBeenCalledWith("trace with spaces");
    expect(response.status).toBe(404); // not found, but no error
  });
});

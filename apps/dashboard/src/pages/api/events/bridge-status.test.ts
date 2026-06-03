import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock processRegistry before any imports
const mockAll: Array<{
  pid: number;
  model: string;
  provider: string;
  status: string;
  startTime: string;
  ssePort?: number;
  stdout?: string;
  stderr?: string;
}> = [];

vi.mock("../../../lib/processRegistry", () => ({
  getAll: () => mockAll,
}));

// Import after mocking
const { GET } = await import("./bridge-status");

const mockContext = {} as any;

describe("GET /api/events/bridge-status", () => {
  beforeEach(() => {
    mockAll.length = 0;
  });

  it("returns 200 OK", async () => {
    const response = await GET(mockContext);
    expect(response.status).toBe(200);
  });

  it("sets Content-Type to application/json", async () => {
    const response = await GET(mockContext);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("has all top-level response fields", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body).toHaveProperty("connected");
    expect(body).toHaveProperty("port");
    expect(body).toHaveProperty("latency_ms");
    expect(body).toHaveProperty("process");
    expect(body).toHaveProperty("bridge");
    expect(body).toHaveProperty("timestamp");
  });

  it("has nested process fields", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.process).toHaveProperty("pid");
    expect(body.process).toHaveProperty("model");
    expect(body.process).toHaveProperty("provider");
    expect(body.process).toHaveProperty("started_at");
    expect(body.process).toHaveProperty("status");
    expect(body.process).toHaveProperty("uptime_seconds");
    expect(body.process).toHaveProperty("stdout_bytes");
    expect(body.process).toHaveProperty("stderr_bytes");
  });

  it("has nested bridge fields", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.bridge).toHaveProperty("default_port");
    expect(body.bridge).toHaveProperty("probe_url");
    expect(body.bridge).toHaveProperty("probe_success");
    expect(body.bridge).toHaveProperty("last_error");
  });

  it("returns connected:false when no bridge is reachable without a running process", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.connected).toBe(false);
    expect(body.port).toBeGreaterThan(0);
    expect(body.latency_ms).toBeTypeOf("number");
    expect(body.process.pid).toBeNull();
    expect(body.process.model).toBeNull();
    expect(body.process.provider).toBeNull();
    expect(body.process.status).toBeNull();
    expect(body.bridge.probe_success).toBe(false);
    expect(body.bridge.last_error).toBeTypeOf("string");
  });

  it("populates process details from a running benchmark", async () => {
    mockAll.push({
      pid: 12345,
      model: "qwen3.5-9b-coder",
      provider: "ollama",
      status: "running",
      startTime: new Date(Date.now() - 60000).toISOString(), // 1 minute ago
      ssePort: 9999,
      stdout: "line1\nline2\n",
      stderr: "",
    });

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.connected).toBe(false);
    expect(body.port).toBe(9999);
    expect(body.process.pid).toBe(12345);
    expect(body.process.model).toBe("qwen3.5-9b-coder");
    expect(body.process.provider).toBe("ollama");
    expect(body.process.status).toBe("running");
    expect(body.process.started_at).toBeTypeOf("string");
    expect(body.process.uptime_seconds).toBeGreaterThanOrEqual(59);
    // "line1\nline2\n" is 12 bytes
    expect(body.process.stdout_bytes).toBe(12);
    expect(body.process.stderr_bytes).toBe(0);
  });

  it("calculates uptime correctly for a recently started process", async () => {
    mockAll.push({
      pid: 11111,
      model: "test-model",
      provider: "lm-studio",
      status: "running",
      startTime: new Date(Date.now() - 5000).toISOString(), // 5 seconds ago
      ssePort: 8000,
      stdout: "",
      stderr: "",
    });

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.process.uptime_seconds).toBeGreaterThanOrEqual(4);
    expect(body.process.uptime_seconds).toBeLessThanOrEqual(6);
  });

  it("ignores exited processes", async () => {
    mockAll.push({
      pid: 33333,
      model: "exited-model",
      provider: "lm-studio",
      status: "exited",
      startTime: new Date().toISOString(),
      ssePort: 8000,
    });

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.process.pid).toBeNull();
    expect(body.process.model).toBeNull();
  });

  it("picks the first running process with an ssePort when multiple exist", async () => {
    mockAll.push(
      {
        pid: 100,
        model: "model-a",
        provider: "lm-studio",
        status: "running",
        startTime: new Date().toISOString(),
        ssePort: 8000,
      },
      {
        pid: 200,
        model: "model-b",
        provider: "ollama",
        status: "running",
        startTime: new Date().toISOString(),
        ssePort: 9000,
      },
    );

    const response = await GET(mockContext);
    const body = await response.json();

    // First match in insertion order wins
    expect(body.process.pid).toBe(100);
    expect(body.process.model).toBe("model-a");
    expect(body.process.provider).toBe("lm-studio");
  });

  it("uses default port when no running process has an ssePort", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.port).toBeGreaterThan(0);
    expect(body.bridge.default_port).toBeGreaterThan(0);
    // Both should match the MODELLENS_SSE_PORT or default 9090
    expect(body.port).toBe(body.bridge.default_port);
  });

  it("has timestamp as a valid ISO 8601 date string", async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    const date = new Date(body.timestamp);
    expect(date.toISOString()).toBe(body.timestamp);
  });

  it("reports probe details including url and success", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.bridge.probe_url).toBeTypeOf("string");
    expect(body.bridge.probe_success).toBe(false);
    expect(body.bridge.last_error).toBeTypeOf("string");
  });
});

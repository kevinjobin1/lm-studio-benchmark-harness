import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock processRegistry before any imports
const mockRunning: Array<{
  pid: number;
  model: string;
  provider: string;
  status: string;
  ssePort?: number;
}> = [];

vi.mock("../../../lib/processRegistry", () => ({
  getAll: () => mockRunning,
}));

// Import after mocking
const { GET } = await import("./health");

// Minimal mock APIContext — the handler doesn't use any context properties
const mockContext = {} as any;

describe("GET /api/events/health", () => {
  beforeEach(() => {
    // Clear mock state between tests
    mockRunning.length = 0;
  });

  it("returns 200 OK", async () => {
    const response = await GET(mockContext);
    expect(response.status).toBe(200);
  });

  it("sets Content-Type to application/json", async () => {
    const response = await GET(mockContext);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns connected:false when no SSE bridge is reachable and no process is running", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.connected).toBe(false);
    expect(body.port).toBeGreaterThan(0);
    expect(body.model).toBeNull();
    expect(body.provider).toBeNull();
    expect(body).toHaveProperty("timestamp");
  });

  it("returns model and provider from a running benchmark process", async () => {
    mockRunning.push({
      pid: 12345,
      model: "qwen3.5-9b-coder",
      provider: "ollama",
      status: "running",
      ssePort: 9999,
    });

    const response = await GET(mockContext);
    const body = await response.json();

    // The bridge at port 9999 won't be reachable, so connected is false
    expect(body.connected).toBe(false);
    expect(body.model).toBe("qwen3.5-9b-coder");
    expect(body.provider).toBe("ollama");
    expect(body.port).toBe(9999);
  });

  it("uses the first running process with an ssePort", async () => {
    mockRunning.push(
      {
        pid: 11111,
        model: "model-a",
        provider: "lm-studio",
        status: "running",
        ssePort: 8000,
      },
      {
        pid: 22222,
        model: "model-b",
        provider: "ollama",
        status: "running",
        ssePort: 9000,
      },
    );

    const response = await GET(mockContext);
    const body = await response.json();

    // Iterates in insertion order (getAll() returns newest-first,
    // but the mock returns insertion order), first match wins
    expect(body.model).toBe("model-a");
    expect(body.provider).toBe("lm-studio");
    expect(body.port).toBe(8000);
  });

  it("ignores exited processes", async () => {
    mockRunning.push({
      pid: 33333,
      model: "exited-model",
      provider: "lm-studio",
      status: "exited",
      ssePort: 8000,
    });

    const response = await GET(mockContext);
    const body = await response.json();

    // No running processes, so falls back to default port (not connected)
    expect(body.connected).toBe(false);
    expect(body.model).toBeNull();
    expect(body.provider).toBeNull();
  });

  it("has all required response fields", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body).toHaveProperty("connected");
    expect(body).toHaveProperty("port");
    expect(body).toHaveProperty("model");
    expect(body).toHaveProperty("provider");
    expect(body).toHaveProperty("timestamp");
  });

  it("has timestamp as a valid ISO 8601 date string", async () => {
    const response = await GET(mockContext);
    const body = await response.json();
    const date = new Date(body.timestamp);
    expect(date.toISOString()).toBe(body.timestamp);
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock loadTraceManifest so we control the SSR-side data
const mockManifest = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    version: "1.0.0",
    generated_at: "2026-06-02T12:00:00Z",
    total_traces: 0,
    traces: [],
  }),
);

vi.mock("../../../lib/loadTraces", () => ({
  loadTraceManifest: mockManifest,
  loadTrace: vi.fn().mockResolvedValue(null),
  loadTraceList: vi.fn().mockResolvedValue([]),
}));

const { GET } = await import("./index");

const mockRequest = (url: string): Request =>
  new Request(url.startsWith("http") ? url : `http://localhost:4321${url}`);

describe("GET /api/traces", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns 200 OK", async () => {
    const response = await GET({
      request: mockRequest("/api/traces"),
      params: {},
    } as any);
    expect(response.status).toBe(200);
  });

  it("sets Content-Type to application/json", async () => {
    const response = await GET({
      request: mockRequest("/api/traces"),
      params: {},
    } as any);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns an array in the body", async () => {
    const response = await GET({
      request: mockRequest("/api/traces"),
      params: {},
    } as any);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
  });

  it("passes model query param to loadTraceList", async () => {
    const { loadTraceList } = await import("../../../lib/loadTraces");
    const response = await GET({
      request: mockRequest("/api/traces?model=llama"),
      params: {},
    } as any);
    await response.json();
    expect(loadTraceList).toHaveBeenCalledWith(
      expect.objectContaining({ model: "llama" }),
    );
  });

  it("passes limit and offset query params", async () => {
    const { loadTraceList } = await import("../../../lib/loadTraces");
    const response = await GET({
      request: mockRequest("/api/traces?limit=10&offset=5"),
      params: {},
    } as any);
    await response.json();
    expect(loadTraceList).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 10, offset: 5 }),
    );
  });

  it("passes status query param", async () => {
    const { loadTraceList } = await import("../../../lib/loadTraces");
    const response = await GET({
      request: mockRequest("/api/traces?status=failed"),
      params: {},
    } as any);
    await response.json();
    expect(loadTraceList).toHaveBeenCalledWith(
      expect.objectContaining({ status: "failed" }),
    );
  });

  it("handles invalid limit gracefully", async () => {
    const response = await GET({
      request: mockRequest("/api/traces?limit=notanumber"),
      params: {},
    } as any);
    const body = await response.json();
    expect(response.status).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });
});

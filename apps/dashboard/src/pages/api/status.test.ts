import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock node:child_process before any imports that use it
vi.mock("node:child_process", () => ({
  spawnSync: vi.fn(),
}));

// Default LM_STUDIO_URL
vi.stubEnv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1");

const { GET } = await import("./status");

const mockContext = {} as any;

beforeEach(() => {
  vi.clearAllMocks();
  // Default: LM Studio is reachable with one model
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ data: [{ id: "gemma-4-e4b" }] }),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("GET /api/status", () => {
  it("returns 200 OK", async () => {
    const response = await GET(mockContext);
    expect(response.status).toBe(200);
  });

  it("sets Content-Type to application/json", async () => {
    const response = await GET(mockContext);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns connected=true and the model list when LM Studio responds", async () => {
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.connected).toBe(true);
    expect(body.models).toEqual(["gemma-4-e4b"]);
    expect(body.provider).toBe("LM Studio");
  });

  it("returns connected=false when LM Studio is unreachable", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Connection refused"));

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.connected).toBe(false);
    expect(body.models).toEqual([]);
    expect(body.error).toBe("Connection refused");
  });

  it("returns connected=false when LM Studio returns non-ok status", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
    });

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.connected).toBe(false);
    expect(body.models).toEqual([]);
    expect(body.error).toContain("503");
  });

  it("fetches from the correct LM Studio URL", async () => {
    await GET(mockContext);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:1234/v1/models",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("includes hardware info when connected", async () => {
    const { spawnSync } = await import("node:child_process");
    (spawnSync as any).mockReturnValue({
      status: 0,
      stdout: JSON.stringify({
        cpu: { model: "Apple M3 Max", cores_physical: 14 },
        memory: { ram_total_mb: 18432 },
      }),
    });

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.hardware).toBeDefined();
    expect(body.hardware.cpu.model).toBe("Apple M3 Max");
  });

  it("returns empty hardware object when spawnSync fails", async () => {
    const { spawnSync } = await import("node:child_process");
    (spawnSync as any).mockReturnValue({
      status: 1,
      stdout: "",
    });

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.hardware).toEqual({});
  });
});

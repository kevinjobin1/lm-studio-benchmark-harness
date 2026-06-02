import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock processRegistry before any imports
vi.mock("../../../lib/processRegistry", () => ({
  getAll: vi.fn(),
}));

const { getAll } = await import("../../../lib/processRegistry");
const { GET } = await import("./active");

const mockContext = {} as any;

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("GET /api/run-benchmark/active", () => {
  it("returns 200 OK", async () => {
    (getAll as any).mockReturnValue([]);
    const response = await GET(mockContext);
    expect(response.status).toBe(200);
  });

  it("sets Content-Type to application/json", async () => {
    (getAll as any).mockReturnValue([]);
    const response = await GET(mockContext);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns active=false when no processes are running", async () => {
    (getAll as any).mockReturnValue([]);
    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.active).toBe(false);
    expect(body.processes).toEqual([]);
  });

  it("returns active=false when all processes have exited", async () => {
    (getAll as any).mockReturnValue([
      { pid: 123, model: "test", quick: false, startTime: "2026-01-01T00:00:00Z", status: "exited", exitCode: 0 },
      { pid: 456, model: "test2", quick: true, startTime: "2026-01-01T00:00:00Z", status: "killed", exitCode: null },
    ]);

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.active).toBe(false);
    expect(body.processes).toEqual([]);
  });

  it("returns active=true with running processes", async () => {
    (getAll as any).mockReturnValue([
      { pid: 789, model: "benchmark", quick: true, startTime: "2026-01-01T00:00:00Z", status: "running", exitCode: null },
    ]);

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.active).toBe(true);
    expect(body.processes).toHaveLength(1);
    expect(body.processes[0]).toEqual({
      pid: 789,
      model: "benchmark",
      quick: true,
      startTime: "2026-01-01T00:00:00Z",
    });
  });

  it("only returns running processes (not exited/killed)", async () => {
    (getAll as any).mockReturnValue([
      { pid: 111, model: "a", quick: false, startTime: "2026-01-01T00:00:00Z", status: "running", exitCode: null },
      { pid: 222, model: "b", quick: true, startTime: "2026-01-01T00:00:00Z", status: "exited", exitCode: 0 },
      { pid: 333, model: "c", quick: true, startTime: "2026-01-01T00:00:00Z", status: "killed", exitCode: null },
      { pid: 444, model: "d", quick: false, startTime: "2026-01-01T00:00:00Z", status: "running", exitCode: null },
    ]);

    const response = await GET(mockContext);
    const body = await response.json();

    expect(body.active).toBe(true);
    expect(body.processes).toHaveLength(2);
    expect(body.processes.map((p: any) => p.pid)).toEqual([111, 444]);
  });
});

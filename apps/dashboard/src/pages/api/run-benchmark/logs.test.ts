import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../../../lib/processRegistry", () => ({
  getByPid: vi.fn(),
}));

const { getByPid } = await import("../../../lib/processRegistry");
const { GET } = await import("./logs");

const mockRunningEntry = {
  pid: 12345,
  model: "benchmark",
  provider: "python",
  quick: true,
  startTime: "2026-06-02T02:25:52.205Z",
  status: "running" as const,
  exitCode: null,
  stdout: "[INFO] Starting benchmark...\n[INFO] Processing...\n",
  stderr: "",
};

function mockContext(overrides?: Record<string, string>): any {
  const params = new URLSearchParams(overrides || { pid: "12345" });
  return { url: { searchParams: params } };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("GET /api/run-benchmark/logs", () => {
  it("returns 200 OK with process logs when pid is valid", async () => {
    (getByPid as any).mockReturnValue(mockRunningEntry);
    const response = await GET(mockContext());
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.pid).toBe(12345);
    expect(body.status).toBe("running");
    expect(body.stdout).toContain("[INFO] Starting benchmark");
    expect(body.stderr).toBe("");
  });

  it("sets Content-Type to application/json", async () => {
    (getByPid as any).mockReturnValue(mockRunningEntry);
    const response = await GET(mockContext());
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns 400 when pid parameter is missing", async () => {
    const response = await GET(mockContext({}));
    expect(response.status).toBe(400);

    const body = await response.json();
    expect(body.error).toBe("Missing pid parameter");
  });

  it("returns 400 when pid is not a number", async () => {
    const response = await GET(mockContext({ pid: "abc" }));
    expect(response.status).toBe(400);

    const body = await response.json();
    expect(body.error).toBe("Invalid pid");
  });

  it("returns 404 when process is not found", async () => {
    (getByPid as any).mockReturnValue(undefined);
    const response = await GET(mockContext({ pid: "99999" }));
    expect(response.status).toBe(404);

    const body = await response.json();
    expect(body.error).toBe("Process not found");
  });

  it("passes the correct pid to getByPid", async () => {
    (getByPid as any).mockReturnValue(mockRunningEntry);
    await GET(mockContext({ pid: "77777" }));

    expect(getByPid).toHaveBeenCalledWith(77777);
  });

  it("returns logs for an exited process", async () => {
    (getByPid as any).mockReturnValue({
      ...mockRunningEntry,
      status: "exited",
      exitCode: 0,
      stderr: "warning: deprecated API call",
    });

    const response = await GET(mockContext({ pid: "11111" }));
    const body = await response.json();

    expect(body.status).toBe("exited");
    expect(body.stderr).toBe("warning: deprecated API call");
  });
});

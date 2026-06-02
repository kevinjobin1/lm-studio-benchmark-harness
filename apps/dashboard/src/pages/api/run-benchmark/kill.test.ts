import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../../../lib/processRegistry", () => ({
  killProcess: vi.fn(),
}));

const { killProcess } = await import("../../../lib/processRegistry");
const { POST } = await import("./kill");

function mockContext(overrides?: Record<string, string>): any {
  const params = new URLSearchParams(overrides || { pid: "12345" });
  return { url: { searchParams: params }, request: {} };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("POST /api/run-benchmark/kill", () => {
  it("returns 200 with success=true when process is killed", async () => {
    (killProcess as any).mockReturnValue(true);

    const response = await POST(mockContext());
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.pid).toBe(12345);
  });

  it("sets Content-Type to application/json", async () => {
    (killProcess as any).mockReturnValue(true);
    const response = await POST(mockContext());
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns 200 with success=false when process is not found", async () => {
    (killProcess as any).mockReturnValue(false);

    const response = await POST(mockContext({ pid: "99999" }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.success).toBe(false);
    expect(body.pid).toBe(99999);
  });

  it("returns 400 when pid parameter is missing", async () => {
    const response = await POST(mockContext({}));
    expect(response.status).toBe(400);

    const body = await response.json();
    expect(body.error).toBe("Missing pid parameter");
  });

  it("returns 400 when pid is not a number", async () => {
    const response = await POST(mockContext({ pid: "abc" }));
    expect(response.status).toBe(400);

    const body = await response.json();
    expect(body.error).toBe("Invalid pid");
  });

  it("passes the correct pid to killProcess", async () => {
    (killProcess as any).mockReturnValue(true);
    await POST(mockContext({ pid: "77777" }));

    expect(killProcess).toHaveBeenCalledWith(77777);
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock child_process.spawn
const mockChildProcess = {
  pid: 12345,
  stdout: { on: vi.fn() },
  stderr: { on: vi.fn() },
  on: vi.fn(),
};
vi.mock("node:child_process", () => ({
  spawn: vi.fn(() => mockChildProcess),
}));

// Mock processRegistry
const mockRegister = vi.fn(() => ({
  pid: 12345,
  model: "benchmark",
  provider: "python",
  quick: true,
  status: "running",
}));
const mockAppendStdout = vi.fn();
const mockAppendStderr = vi.fn();
const mockMarkExited = vi.fn();

vi.mock("../../../lib/processRegistry", () => ({
  register: (...args: any[]) => mockRegister(...args),
  appendStdout: (...args: any[]) => mockAppendStdout(...args),
  appendStderr: (...args: any[]) => mockAppendStderr(...args),
  markExited: (...args: any[]) => mockMarkExited(...args),
}));

const { POST } = await import("./index");

function mockContext(body?: any): any {
  return {
    request: {
      json: () => (body !== undefined ? Promise.resolve(body) : Promise.reject(new Error("No body"))),
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("POST /api/run-benchmark", () => {
  it("returns 200 with success=true and a pid", async () => {
    const response = await POST(mockContext({ quick: true }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.pid).toBe(12345);
    expect(body.message).toContain("PID 12345");
  });

  it("sets Content-Type to application/json", async () => {
    const response = await POST(mockContext({ quick: true }));
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("spawns python3 with bench_apple_silicon_v2.py --quick for quick mode", async () => {
    const { spawn } = await import("node:child_process");

    await POST(mockContext({ quick: true }));

    expect(spawn).toHaveBeenCalledWith(
      "python3",
      ["bench_apple_silicon_v2.py", "--quick"],
      expect.objectContaining({
        detached: true,
        stdio: ["ignore", "pipe", "pipe"],
      }),
    );
  });

  it("spawns python3 without --quick when quick=false", async () => {
    const { spawn } = await import("node:child_process");

    await POST(mockContext({ quick: false }));

    expect(spawn).toHaveBeenCalledWith(
      "python3",
      ["bench_apple_silicon_v2.py"],
      expect.anything(),
    );
  });

  it("defaults to quick mode when no body is provided", async () => {
    // Mock context where request.json() rejects
    const ctx = {
      request: {
        json: () => Promise.reject(new Error("No body")),
      },
    };

    const { spawn } = await import("node:child_process");
    await POST(ctx);

    expect(spawn).toHaveBeenCalledWith(
      "python3",
      ["bench_apple_silicon_v2.py", "--quick"],
      expect.anything(),
    );
  });

  it("registers the process in the registry", async () => {
    await POST(mockContext({ quick: true }));

    expect(mockRegister).toHaveBeenCalledWith(
      12345,
      expect.objectContaining({
        model: "benchmark",
        quick: true,
      }),
      mockChildProcess,
    );
  });

  it("attaches stdout/stderr listeners and exit handler", async () => {
    await POST(mockContext({ quick: true }));

    expect(mockChildProcess.stdout.on).toHaveBeenCalledWith("data", expect.any(Function));
    expect(mockChildProcess.stderr.on).toHaveBeenCalledWith("data", expect.any(Function));
    expect(mockChildProcess.on).toHaveBeenCalledWith("exit", expect.any(Function));
    expect(mockChildProcess.on).toHaveBeenCalledWith("error", expect.any(Function));
  });

  it("returns 500 when child.pid is undefined", async () => {
    const { spawn } = await import("node:child_process");
    (spawn as any).mockReturnValue({
      pid: undefined,
      stdout: { on: vi.fn() },
      stderr: { on: vi.fn() },
      on: vi.fn(),
    });

    const response = await POST(mockContext({ quick: true }));
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body.success).toBe(false);
    expect(body.message).toBe("Failed to spawn process");
  });
});

// @vitest-environment node
import { describe, it, expect, vi, beforeEach, afterEach, afterAll } from "vitest";

vi.useFakeTimers();

// Track pids we register so we can clean them up between tests
const registeredPids: number[] = [];

import {
  register,
  getByPid,
  getAll,
  markExited,
  killProcess,
  appendStdout,
  appendStderr,
} from "./processRegistry";

// Helper: a partial child process mock for killProcess tests
function mockChild(pid: number) {
  return {
    pid,
    kill: vi.fn(),
  } as any;
}

// Helper: register a process and track it for cleanup
function trackRegister(pid: number, overrides: Record<string, any> = {}) {
  registeredPids.push(pid);
  return register(
    pid,
    {
      model: overrides.model ?? "test-model",
      provider: overrides.provider ?? "python",
      quick: overrides.quick ?? true,
      startTime: overrides.startTime ?? new Date().toISOString(),
    },
    overrides.child ?? undefined,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  registeredPids.length = 0;
});

afterEach(() => {
  // Force-clean any remaining entries by re-registering as running with a mock child,
  // then using killProcess to set up the cleanup timer, then firing it.
  for (const pid of registeredPids) {
    if (getByPid(pid)) {
      const mock = { pid, kill: vi.fn() } as any;
      register(
        pid,
        { model: "cleanup", provider: "cleanup", quick: true, startTime: new Date().toISOString() },
        mock,
      );
      killProcess(pid);
    }
  }
  vi.runAllTimers();

  for (const pid of registeredPids) {
    expect(getByPid(pid)).toBeUndefined();
  }

  vi.restoreAllMocks();
});

afterAll(() => {
  vi.useRealTimers();
});

describe("register", () => {
  it("creates an entry with default fields", () => {
    const entry = trackRegister(1001);
    expect(entry).toMatchObject({
      pid: 1001,
      model: "test-model",
      provider: "python",
      quick: true,
      status: "running",
      exitCode: null,
      stdout: "",
      stderr: "",
    });
    expect(entry.startTime).toBeDefined();
  });

  it("returns the entry so it can be retrieved by pid", () => {
    trackRegister(1002);
    const retrieved = getByPid(1002);
    expect(retrieved).toBeDefined();
    expect(retrieved!.pid).toBe(1002);
  });

  it("stores the child process reference when provided", () => {
    const child = mockChild(9001);
    trackRegister(1003, { child });
    const entry = getByPid(1003);
    expect(entry!._child).toBe(child);
  });
});

describe("getByPid", () => {
  it("returns undefined for an unknown pid", () => {
    expect(getByPid(99999)).toBeUndefined();
  });

  it("returns the entry for a known pid", () => {
    trackRegister(2001);
    const entry = getByPid(2001);
    expect(entry).toBeDefined();
    expect(entry!.pid).toBe(2001);
  });
});

describe("getAll", () => {
  it("returns an empty array when no processes are registered", () => {
    const all = getAll();
    expect(all).toEqual([]);
  });

  it("returns all registered entries sorted by startTime descending", () => {
    const early = new Date("2026-01-01T00:00:00Z").toISOString();
    const late = new Date("2026-06-01T00:00:00Z").toISOString();

    trackRegister(3001, { startTime: late });
    trackRegister(3002, { startTime: early });

    const all = getAll();
    expect(all).toHaveLength(2);
    expect(all[0].pid).toBe(3001); // later startTime first
    expect(all[1].pid).toBe(3002);
  });
});

describe("markExited", () => {
  it("marks a running process as exited with exit code", () => {
    trackRegister(4001);
    markExited(4001, 0);

    const entry = getByPid(4001);
    expect(entry!.status).toBe("exited");
    expect(entry!.exitCode).toBe(0);
  });

  it("marks with a non-zero exit code", () => {
    trackRegister(4002);
    markExited(4002, 1);

    const entry = getByPid(4002);
    expect(entry!.status).toBe("exited");
    expect(entry!.exitCode).toBe(1);
  });

  it("does not overwrite 'killed' status with 'exited'", () => {
    trackRegister(4003);
    const child = mockChild(4003);
    const killSpy = vi.spyOn(process, "kill").mockImplementation(() => true);
    killProcess(4003);
    killSpy.mockRestore();

    markExited(4003, 0);

    const entry = getByPid(4003);
    expect(entry!.status).toBe("killed");
  });

  it("is a no-op for unknown pid", () => {
    expect(() => markExited(99999, 0)).not.toThrow();
  });
});

describe("killProcess", () => {
  it("returns false for unknown pid", () => {
    const result = killProcess(99999);
    expect(result).toBe(false);
  });

  it("returns false for an already-exited process", () => {
    trackRegister(5001);
    markExited(5001, 0);
    const result = killProcess(5001);
    expect(result).toBe(false);
  });

  it("marks the entry as killed", () => {
    const child = mockChild(5555);
    trackRegister(5002, { child });

    const killSpy = vi.spyOn(process, "kill").mockImplementation(() => true);
    const result = killProcess(5002);
    expect(result).toBe(true);

    const entry = getByPid(5002);
    expect(entry!.status).toBe("killed");

    killSpy.mockRestore();
  });

  it("sends SIGTERM to the process group", () => {
    const child = mockChild(5555);
    trackRegister(5003, { child });

    const killSpy = vi.spyOn(process, "kill").mockImplementation(() => true);
    killProcess(5003);
    expect(killSpy).toHaveBeenCalledWith(-5555, "SIGTERM");

    killSpy.mockRestore();
  });

  it("falls back to child.kill() when process.kill throws", () => {
    const child = mockChild(5555);
    trackRegister(5004, { child });

    const killSpy = vi.spyOn(process, "kill").mockImplementation(() => {
      throw new Error("EPERM");
      return true;
    });

    killProcess(5004);
    expect(child.kill).toHaveBeenCalledWith("SIGTERM");

    killSpy.mockRestore();
  });

  it("is idempotent (second call returns false)", () => {
    const child = mockChild(5555);
    trackRegister(5005, { child });

    const killSpy = vi.spyOn(process, "kill").mockImplementation(() => true);
    expect(killProcess(5005)).toBe(true);
    expect(killProcess(5005)).toBe(false);

    killSpy.mockRestore();
  });

  it("escalates to SIGKILL after 5 seconds if still killed", () => {
    const child = mockChild(5555);
    trackRegister(5006, { child });

    const killSpy = vi.spyOn(process, "kill").mockImplementation(() => true);
    killProcess(5006);

    expect(killSpy).toHaveBeenCalledTimes(1);
    expect(killSpy).toHaveBeenCalledWith(-5555, "SIGTERM");

    vi.advanceTimersByTime(5000);
    expect(killSpy).toHaveBeenCalledTimes(2);
    // Should also include SIGKILL
    const sigkillCall = killSpy.mock.calls.find(
      ([, sig]) => sig === "SIGKILL",
    );
    expect(sigkillCall).toBeDefined();

    killSpy.mockRestore();
  });

  it("cleans up the entry from the registry after 30 seconds", () => {
    const child = mockChild(5555);
    trackRegister(5007, { child });

    const killSpy = vi.spyOn(process, "kill").mockImplementation(() => true);
    killProcess(5007);

    // Entry still exists after kill
    expect(getByPid(5007)).toBeDefined();

    // Advance 30 seconds — cleanup timer fires
    vi.advanceTimersByTime(30000);
    expect(getByPid(5007)).toBeUndefined();

    killSpy.mockRestore();
  });

  it("handles a running process with no child (_child is undefined)", () => {
    trackRegister(5008);

    const result = killProcess(5008);
    expect(result).toBe(true);

    const entry = getByPid(5008);
    expect(entry!.status).toBe("killed");

    // After 30s, it should be cleaned up
    vi.advanceTimersByTime(30000);
    expect(getByPid(5008)).toBeUndefined();
  });
});

describe("appendStdout / appendStderr", () => {
  it("appends stdout to a registered process", () => {
    trackRegister(6001);
    appendStdout(6001, "line1\n");
    appendStdout(6001, "line2\n");

    const entry = getByPid(6001);
    expect(entry!.stdout).toBe("line1\nline2\n");
  });

  it("appends stderr to a registered process", () => {
    trackRegister(6002);
    appendStderr(6002, "error: something\n");
    appendStderr(6002, "warning: deprecated\n");

    const entry = getByPid(6002);
    expect(entry!.stderr).toBe("error: something\nwarning: deprecated\n");
  });

  it("is a no-op for unknown pid", () => {
    expect(() => appendStdout(99999, "data")).not.toThrow();
    expect(() => appendStderr(99999, "data")).not.toThrow();
  });

  it("truncates stdout when exceeding MAX_LOG_CHARS", () => {
    const chunk = "x".repeat(150_000);
    trackRegister(6003);

    appendStdout(6003, chunk);
    expect(getByPid(6003)!.stdout.length).toBe(150_000);

    // Second chunk: total = 300k > 200k limit → truncate to last 100k
    // 300k string, last 100k = positions 200k-299k
    // That's within the second chunk starting at position 50k: chunk.slice(50_000)
    appendStdout(6003, chunk);
    expect(getByPid(6003)!.stdout.length).toBe(100_000);
    expect(getByPid(6003)!.stdout).toBe(chunk.slice(50_000));
  });

  it("truncates stderr when exceeding MAX_LOG_CHARS", () => {
    const chunk = "x".repeat(150_000);
    trackRegister(6004);

    appendStderr(6004, chunk);
    expect(getByPid(6004)!.stderr.length).toBe(150_000);

    appendStderr(6004, chunk);
    expect(getByPid(6004)!.stderr.length).toBe(100_000);
    expect(getByPid(6004)!.stderr).toBe(chunk.slice(50_000));
  });
});

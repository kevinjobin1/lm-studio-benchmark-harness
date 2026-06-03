/**
 * In-memory registry for spawned benchmark processes.
 * Shared between the POST /api/run-benchmark endpoint (registers)
 * and the GET /api/run-benchmark/logs endpoint (reads).
 */

import type { ChildProcess } from "node:child_process";

export interface ProcessEntry {
  pid: number;
  model: string;
  provider: string;
  quick: boolean;
  startTime: string;
  status: "running" | "exited" | "killed";
  exitCode: number | null;
  stdout: string;
  stderr: string;
  /** Port of the SSE event bridge (if the process started one). */
  ssePort?: number;
  _child?: ChildProcess;
  _killTimer?: ReturnType<typeof setTimeout>;
  _cleanupTimer?: ReturnType<typeof setTimeout>;
}

const registry = new Map<number, ProcessEntry>();

// Auto-clean entries older than 1 hour
const MAX_AGE_MS = 60 * 60 * 1000;

function pruneOld() {
  const now = Date.now();
  for (const [pid, entry] of registry) {
    if ((entry.status === "exited" || entry.status === "killed") && now - new Date(entry.startTime).getTime() > MAX_AGE_MS) {
      registry.delete(pid);
    }
  }
}

export function register(pid: number, entry: Omit<ProcessEntry, "pid" | "stdout" | "stderr" | "status" | "exitCode" | "_child">, child?: ChildProcess): ProcessEntry {
  pruneOld();
  const full: ProcessEntry = {
    pid,
    ...entry,
    status: "running",
    exitCode: null,
    stdout: "",
    stderr: "",
    _child: child,
  };
  registry.set(pid, full);
  return full;
}

export function getByPid(pid: number): ProcessEntry | undefined {
  pruneOld();
  return registry.get(pid);
}

export function getAll(): ProcessEntry[] {
  pruneOld();
  return [...registry.values()].sort(
    (a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime()
  );
}

export function markExited(pid: number, exitCode: number | null): void {
  const entry = registry.get(pid);
  if (entry) {
    // Don't overwrite "killed" status — the kill endpoint already set it
    if (entry.status !== "killed") {
      entry.status = "exited";
    }
    entry.exitCode = exitCode;
    // Clear only the SIGKILL escalation timer; keep the cleanup timer running
    // so the entry still gets removed from the registry after 30s.
    if (entry._killTimer) {
      clearTimeout(entry._killTimer);
      entry._killTimer = undefined;
    }
  }
}

/**
 * Kill a running process by PID. Returns true if a signal was sent.
 * Escalates: SIGTERM → (5s) → SIGKILL → (30s) → registry removal.
 * Idempotent — calling twice on the same pid is a no-op after the first.
 */
export function killProcess(pid: number): boolean {
  const entry = registry.get(pid);
  if (!entry || entry.status !== "running") return false;

  // Guard against double-kill
  entry.status = "killed";
  entry.exitCode = null;

  // Clear any stale timers first
  clearKillTimers(entry);

  if (entry._child && entry._child.pid) {
    // Kill the process group (negative pid) to catch child processes too
    try {
      process.kill(-entry._child.pid, "SIGTERM");
    } catch {
      // Fallback: kill just the direct child
      entry._child.kill("SIGTERM");
    }

    // Escalate to SIGKILL after 5s if process hasn't exited
    entry._killTimer = setTimeout(() => {
      if (entry.status === "killed") {
        try {
          process.kill(-entry._child!.pid!, "SIGKILL");
        } catch {
          entry._child?.kill("SIGKILL");
        }
      }
      entry._killTimer = undefined;
    }, 5000);
  }

  // Clean up from registry after 30s
  entry._cleanupTimer = setTimeout(() => {
    registry.delete(pid);
  }, 30_000);

  return true;
}

/** Clear pending kill escalation + cleanup timers on an entry. */
function clearKillTimers(entry: ProcessEntry): void {
  if (entry._killTimer) {
    clearTimeout(entry._killTimer);
    entry._killTimer = undefined;
  }
  if (entry._cleanupTimer) {
    clearTimeout(entry._cleanupTimer);
    entry._cleanupTimer = undefined;
  }
}

const MAX_LOG_CHARS = 200_000;

export function appendStdout(pid: number, chunk: string): void {
  const entry = registry.get(pid);
  if (!entry) return;
  entry.stdout += chunk;
  if (entry.stdout.length > MAX_LOG_CHARS) {
    entry.stdout = entry.stdout.slice(-MAX_LOG_CHARS / 2);
  }
}

export function appendStderr(pid: number, chunk: string): void {
  const entry = registry.get(pid);
  if (!entry) return;
  entry.stderr += chunk;
  if (entry.stderr.length > MAX_LOG_CHARS) {
    entry.stderr = entry.stderr.slice(-MAX_LOG_CHARS / 2);
  }
}

/**
 * GET /api/run-benchmark/logs?pid=<pid>
 * Returns stdout/stderr from a spawned benchmark process.
 *
 * Without ?pid=: returns all recent processes.
 * With ?pid=123: returns logs for that specific process.
 */

import type { APIRoute } from "astro";
import { getByPid, getAll, type ProcessEntry } from "../../../lib/processRegistry";

export const GET: APIRoute = async ({ url }) => {
  const pidParam = url.searchParams.get("pid");

  if (pidParam) {
    const pid = parseInt(pidParam, 10);
    if (isNaN(pid)) {
      return new Response(
        JSON.stringify({ error: "Invalid pid parameter" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    const entry = getByPid(pid);
    if (!entry) {
      return new Response(
        JSON.stringify({ error: `No process found with pid ${pid}. It may have been cleaned up (entries expire after 1 hour).` }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      );
    }

    return new Response(
      JSON.stringify({
        pid: entry.pid,
        model: entry.model,
        quick: entry.quick,
        startTime: entry.startTime,
        status: entry.status,
        exitCode: entry.exitCode,
        stdout: entry.stdout,
        stderr: entry.stderr,
        stdoutLines: entry.stdout.split("\n").length,
        stderrLines: entry.stderr.split("\n").length,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }

  // No pid — return summary of all recent processes
  const all = getAll();
  return new Response(
    JSON.stringify({
      processes: all.map((e: ProcessEntry) => ({
        pid: e.pid,
        model: e.model,
        quick: e.quick,
        startTime: e.startTime,
        status: e.status,
        exitCode: e.exitCode,
        stdoutChars: e.stdout.length,
        stderrChars: e.stderr.length,
      })),
      total: all.length,
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
};

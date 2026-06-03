import type { APIRoute } from "astro";
import { spawn } from "node:child_process";
import { register, appendStdout, appendStderr, markExited } from "../../../lib/processRegistry";

export const POST: APIRoute = async ({ request }) => {
  let quick = true;
  try {
    const body = await request.json();
    quick = body.quick !== false;
  } catch {
    // default to quick mode
  }

  // Spawn the benchmark CLI — use bench_apple_silicon_v2.py as default
  const cwd = process.cwd();
  // Walk up to project root if inside apps/dashboard
  const projectRoot = cwd.endsWith("apps/dashboard")
    ? cwd.replace(/\/apps\/dashboard$/, "")
    : cwd;

  const args = quick
    ? ["bench_apple_silicon_v2.py", "--quick"]
    : ["bench_apple_silicon_v2.py"];

  // Enable SSE event bridge for real-time dashboard updates
  const SSE_PORT = parseInt(process.env.MODELLENS_SSE_PORT || "9090", 10);
  args.push("--sse-port", String(SSE_PORT));

  const child = spawn("python3", args, {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,   // run in its own process group so SIGTERM hits children
  });

  // Give the child a chance to start before we check pid
  if (child.pid === undefined) {
    return new Response(
      JSON.stringify({ success: false, message: "Failed to spawn process" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  const entry = register(child.pid, {
    model: "benchmark",
    provider: "python",
    quick,
    startTime: new Date().toISOString(),
  }, child);

  // Collect stdout/stderr
  child.stdout?.on("data", (chunk: Buffer) => {
    const text = chunk.toString();
    appendStdout(child.pid!, text);

    // Parse SSE_PORT from stdout — the Python process prints SSE_PORT:XXXX on start
    const match = text.match(/SSE_PORT:(\d+)/);
    if (match && entry) {
      entry.ssePort = parseInt(match[1], 10);
    }
  });
  child.stderr?.on("data", (chunk: Buffer) => {
    appendStderr(child.pid!, chunk.toString());
  });
  child.on("exit", (code) => {
    markExited(child.pid!, code);
  });
  child.on("error", () => {
    markExited(child.pid!, null);
  });

  return new Response(
    JSON.stringify({
      success: true,
      pid: child.pid,
      ssePort: SSE_PORT,
      message: `Benchmark started (PID ${child.pid}, quick=${quick})`,
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

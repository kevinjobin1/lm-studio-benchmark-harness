/**
 * POST /api/run-benchmark
 * Trigger a benchmark run via the Python CLI.
 *
 * Body: { model?: string, quick?: boolean }
 * Response: { success: boolean, message: string, model: string }
 */

import type { APIRoute } from "astro";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
import { register, appendStdout, appendStderr, markExited } from "../../lib/processRegistry";

// Resolve project root relative to this file: apps/dashboard/src/pages/api/ → ../../../../../ → project root
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "..", "..", "..", "..", "..");

const SAFE_MODEL_RE = /^[a-zA-Z0-9._\-\/]+$/;

export const POST: APIRoute = async ({ request }) => {
  try {
    const body = await request.json().catch(() => ({}));
    const quick = body.quick !== false; // default to true

    // ── Auto-detect provider + model ───────────────────────────
    let model = body.model || "";
    let provider = body.provider || "";

    // Try LM Studio first, then Ollama
    try {
      const lmResp = await fetch("http://localhost:1234/v1/models", {
        signal: AbortSignal.timeout(3000),
      });
      if (lmResp.ok) {
        const data = await lmResp.json();
        const loadedModels: string[] = (data.data || []).map(
          (m: { id: string }) => m.id,
        );
        if (loadedModels.length > 0) {
          provider = provider || "lm-studio";
          if (!model) model = loadedModels[0];
        }
      }
    } catch { /* LM Studio not reachable */ }

    if (!provider) {
      try {
        const ollamaResp = await fetch("http://localhost:11434/api/tags", {
          signal: AbortSignal.timeout(3000),
        });
        if (ollamaResp.ok) {
          const data = await ollamaResp.json();
          const ollamaModels = (data.models || []).map((m: { name: string }) => m.name);
          if (ollamaModels.length > 0) {
            provider = "ollama";
            if (!model) model = ollamaModels[0];
          }
        }
      } catch { /* Ollama not reachable */ }
    }

    if (!model) {
      return new Response(
        JSON.stringify({
          success: false,
          message:
            "No model detected. Please load a model in LM Studio or Ollama first.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    // Validate model name to prevent argument injection
    if (!SAFE_MODEL_RE.test(model)) {
      return new Response(
        JSON.stringify({
          success: false,
          message: `Invalid model name: "${model}". Use only alphanumeric, dots, dashes, underscores, and slashes.`,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    // ── Build CLI command ──────────────────────────────────────────
    const args = [
      resolve(PROJECT_ROOT, "apps", "cli", "modellens.py"),
      "run",
      "--framework", "general",
      "--provider", provider || "lm-studio",
      "--model-name",
      model,
      "--ci",
    ];
    if (quick) args.push("--quick");

    console.log(`[run-benchmark] Spawning in ${PROJECT_ROOT}: python3 ${args.join(" ")}`);

    // ── Spawn benchmark process ────────────────────────────────────
    const child = spawn("python3", args, {
      cwd: PROJECT_ROOT,
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
    });

    // Detect spawn failure before responding to client
    const spawnFailed = await new Promise<boolean>((resolve) => {
      child.on("error", () => resolve(true));
      // "spawn" event fires when the OS successfully creates the process
      child.on("spawn", () => resolve(false));
      // Timeout fallback — if neither event fires, treat as success
      setTimeout(() => resolve(false), 500);
    });

    if (spawnFailed) {
      return new Response(
        JSON.stringify({
          success: false,
          message: "Failed to spawn python3. Is Python 3 installed and benchmark.py present?",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    // Register in shared process registry (with child ref for kill support)
    const pid = child.pid!;
    register(pid, {
      model,
      provider: provider || "auto-detected",
      quick,
      startTime: new Date().toISOString(),
    }, child);

    child.stdout?.on("data", (chunk: Buffer) => {
      appendStdout(pid, chunk.toString());
    });
    child.stderr?.on("data", (chunk: Buffer) => {
      appendStderr(pid, chunk.toString());
    });

    child.on("error", (err: Error) => {
      console.error(`[run-benchmark] Process error: ${err.message}`);
      markExited(pid, -1);
    });

    child.on("close", (code: number | null) => {
      markExited(pid, code);
      console.log(
        `[run-benchmark] Process ${pid} exited with code ${code}`,
      );
    });

    // Don't wait — return immediately with the PID
    return new Response(
      JSON.stringify({
        success: true,
        message: `Benchmark started for ${model}${quick ? " (quick mode)" : ""} on ${provider || "auto-detected"}. View logs at /api/run-benchmark/logs?pid=${pid}.`,
        model,
        pid,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  } catch (err) {
    console.error("[run-benchmark] Error:", err);
    return new Response(
      JSON.stringify({
        success: false,
        message: `Server error: ${(err as Error).message}`,
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
};

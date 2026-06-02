import type { APIRoute } from "astro";

// Configurable via LM_STUDIO_URL env var (default: http://127.0.0.1:1234/v1)
const LM_STUDIO_BASE = (import.meta.env.LM_STUDIO_URL as string) || "http://127.0.0.1:1234/v1";

async function checkLmStudio(): Promise<{ connected: boolean; models: string[]; error?: string }> {
  try {
    const resp = await fetch(`${LM_STUDIO_BASE}/models`, { signal: AbortSignal.timeout(3000) });
    if (!resp.ok) {
      return { connected: false, models: [], error: `LM Studio returned ${resp.status}` };
    }
    const data: { data?: { id: string }[] } = await resp.json();
    const models = (data.data || []).map((m) => m.id);
    return { connected: true, models };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return { connected: false, models: [], error: message };
  }
}

/** Resolve project root (works when cwd is project root or apps/dashboard). */
function resolveProjectRoot(): string {
  const cwd = process.cwd();
  if (cwd.endsWith("apps/dashboard")) {
    return cwd.replace(/\/apps\/dashboard$/, "");
  }
  if (cwd.endsWith("apps")) {
    return cwd.replace(/\/apps$/, "");
  }
  return cwd;
}

/** Gather hardware info from the Python CLI (non-blocking best-effort). */
async function getHardware(): Promise<Record<string, unknown>> {
  try {
    const { spawnSync } = await import("node:child_process");
    const projectRoot = resolveProjectRoot();
    const result = spawnSync("python3", [
      "-c",
      `import sys; sys.path.insert(0, '${projectRoot}'); sys.path.insert(0, '${projectRoot}/apps/cli'); from core.hardware import detect_hardware; import json; hw = detect_hardware(); print(json.dumps(hw.to_dict()))`,
    ], {
      cwd: projectRoot,
      timeout: 5000,
      encoding: "utf-8",
    });
    if (result.status === 0 && result.stdout) {
      return JSON.parse(result.stdout);
    }
  } catch {
    // best-effort
  }
  return {};
}

export const GET: APIRoute = async () => {
  const status = await checkLmStudio();
  const hardware = status.connected ? await getHardware() : {};

  return new Response(
    JSON.stringify({
      connected: status.connected,
      models: status.models,
      provider: "LM Studio",
      error: status.error,
      hardware,
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

import type { APIRoute } from "astro";

// Configurable via LM_STUDIO_URL env var (default: http://127.0.0.1:1234/v1)
const LM_STUDIO_BASE = (import.meta.env.LM_STUDIO_URL as string) || "http://127.0.0.1:1234/v1";

/** Refresh interval for cached hardware data (seconds). */
const HARDWARE_CACHE_TTL = 60;

// ── Hardware cache ────────────────────────────────────────────────

let _hwCache: {
  data: Record<string, unknown>;
  timestamp: number;
} | null = null;

function getHardwareFromCache(): Record<string, unknown> | null {
  if (!_hwCache) return null;
  const age = (Date.now() - _hwCache.timestamp) / 1000;
  if (age > HARDWARE_CACHE_TTL) {
    _hwCache = null;
    return null;
  }
  return _hwCache.data;
}

function getHardwareCacheAge(): number | null {
  if (!_hwCache) return null;
  return (Date.now() - _hwCache.timestamp) / 1000;
}

function setHardwareCache(data: Record<string, unknown>): void {
  _hwCache = { data, timestamp: Date.now() };
}

// ── LM Studio health check ────────────────────────────────────────

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

// ── Project root resolution ───────────────────────────────────────

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

// ── Hardware detection (Python) ────────────────────────────────────

/** Gather hardware info from the Python CLI. */
async function getHardwareFromPython(): Promise<Record<string, unknown> | null> {
  try {
    const { spawnSync } = await import("node:child_process");
    const projectRoot = resolveProjectRoot();

    // detect_hardware lives at packages/core/hardware.py —
    // add projectRoot/packages to sys.path so "from core.hardware" resolves
    const pythonScript = [
      "import sys",
      `sys.path.insert(0, '${projectRoot}/packages')`,
      `sys.path.insert(0, '${projectRoot}')`,
      "from core.hardware import detect_hardware",
      "import json",
      "hw = detect_hardware()",
      "print(json.dumps(hw.to_dict()))",
    ].join("; ");

    const result = spawnSync("python3", ["-c", pythonScript], {
      cwd: projectRoot,
      timeout: 5000,
      encoding: "utf-8",
    });
    if (result.status === 0 && result.stdout) {
      return JSON.parse(result.stdout) as Record<string, unknown>;
    }
  } catch {
    // best-effort — will try systeminformation fallback
  }
  return null;
}

// ── Hardware detection (systeminformation fallback) ────────────────

/** Gather hardware info using the systeminformation npm package.
 *
 * Called when Python is unavailable (e.g., Cloudflare Workers
 * deployment where ``node:child_process`` isn't available or
 * ``python3`` isn't on PATH).
 */
async function getHardwareFromSystemInfo(): Promise<Record<string, unknown>> {
  try {
    const si = await import("systeminformation");

    const [cpu, mem, osInfo, system] = await Promise.all([
      si.cpu(),
      si.mem(),
      si.osInfo(),
      si.system(),
    ]);

    return {
      platform: `${osInfo.distro} ${osInfo.release} ${osInfo.arch}`,
      processor: `${cpu.manufacturer} ${cpu.brand}`,
      architecture: osInfo.arch || "unknown",
      memory_gb: Math.round(mem.total / (1024 ** 3)),
    };
  } catch {
    // systeminformation also unavailable — return empty
    return {};
  }
}

// ── Unified hardware resolver ─────────────────────────────────────

/**
 * Resolve hardware info, preferring cached → Python → systeminformation.
 *
 * On first call: runs Python detection (~2-5s), caches for 60s.
 * Subsequent calls within TTL: instant (<1ms) from cache.
 * Python unavailable: falls back to systeminformation npm (~200ms).
 */
async function resolveHardware(): Promise<Record<string, unknown>> {
  // 1. Cache hit (within TTL) — instant
  const cached = getHardwareFromCache();
  if (cached) return cached;

  // 2. Python detection (preferred — most accurate, detects Apple Silicon GPU/ANE)
  const pythonHw = await getHardwareFromPython();
  if (pythonHw) {
    setHardwareCache(pythonHw);
    return pythonHw;
  }

  // 3. systeminformation fallback (works in pure Node.js / unsupported envs)
  const siHw = await getHardwareFromSystemInfo();
  setHardwareCache(siHw);
  return siHw;
}

// ── API Route ─────────────────────────────────────────────────────

export const GET: APIRoute = async () => {
  const status = await checkLmStudio();
  const hardware = status.connected ? await resolveHardware() : {};
  const cacheAge = getHardwareCacheAge();
  const cacheFresh = cacheAge !== null && cacheAge < HARDWARE_CACHE_TTL;

  return new Response(
    JSON.stringify({
      connected: status.connected,
      models: status.models,
      provider: "LM Studio",
      error: status.error,
      hardware,
      hardware_cache: {
        fresh: cacheFresh,
        age_seconds: cacheAge ? Math.round(cacheAge) : null,
        ttl_seconds: HARDWARE_CACHE_TTL,
      },
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
};

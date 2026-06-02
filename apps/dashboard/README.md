# LM Bench Dashboard

Live dashboard for LM Studio Benchmark results — model comparison, radar charts, failure heatmaps, and an interactive benchmark runner.

## Quick Start

```bash
bun install
bun run dev       # → http://localhost:4321
```

The dev server requires **Astro 6** with `@astrojs/node` adapter (`output: "server"`). The dashboard connects to [LM Studio](http://lmstudio.ai) for live status.

### LM Studio URL

The API endpoint checks LM Studio at `http://127.0.0.1:1234/v1` by default. To use a different host/port, set the `LM_STUDIO_URL` environment variable:

```bash
LM_STUDIO_URL=http://192.168.1.50:1234/v1 bun run dev
```

Or add it to a `.env` file in the `apps/dashboard/` directory:

```
LM_STUDIO_URL=http://192.168.1.50:1234/v1
```

See `.env.example` for the variable reference.

---

## API Endpoints

The dashboard includes server-side API endpoints that power the live UI components. All endpoints return JSON.

| Endpoint | Method | Description | Used By |
|----------|--------|-------------|---------|
| `/api/status` | GET | Checks LM Studio connection. Returns `{ connected, models[], provider, hardware }` | `ConnectionStatusBadge`, `RunBenchmarkButton` |
| `/api/run-benchmark` | POST | Starts a benchmark process. Body: `{ quick: boolean }`. Returns `{ success, pid, message }` | `RunBenchmarkButton` |
| `/api/run-benchmark/active` | GET | Lists currently running benchmark processes. Returns `{ active, processes[] }` | `BenchmarkStatusBadge` |
| `/api/run-benchmark/logs?pid=X` | GET | Returns live stdout/stderr for a process. Returns `{ pid, status, stdout, stderr }` | `RunBenchmarkButton` (live logs panel) |
| `/api/run-benchmark/kill?pid=X` | POST | Kills a running process (SIGTERM → 5s → SIGKILL). Returns `{ success, pid }` | `BenchmarkStatusBadge` (stop button) |

### `/api/status` Response Example

```json
{
  "connected": true,
  "models": ["google/gemma-4-e4b"],
  "provider": "LM Studio",
  "hardware": {
    "cpu": { "model": "Apple M3 Max" },
    "memory": { "ram_total_mb": 18432 },
    "os": { "name": "Darwin", "version": "24.0.0" }
  }
}
```

The `hardware` field is populated by running `detect_hardware()` from the Python project. It's best-effort — if the Python call fails (e.g., wrong cwd), hardware returns an empty object `{}` and the badge still shows connection status without hardware info.

### Process Registry

Benchmark processes are tracked in-memory via `src/lib/processRegistry.ts`. Entries auto-expire 1 hour after completion. The registry supports:

- Process spawning with process-group management (`detached: true`)
- Live stdout/stderr streaming (capped at 200 KB per stream)
- Graceful kill escalation: `SIGTERM` → 5s → `SIGKILL`
- Idempotent kill — calling kill twice on the same PID is a no-op

---

## Using the Run Benchmark Button

The **Run new benchmark** button (top-right toolbar) opens a dialog for starting benchmarks:

1. **Connection check** — Opens and immediately checks LM Studio availability. If LM Studio isn't running, you'll see a "Not connected" error.
2. **Quick mode** — Toggle on for faster runs with fewer samples. Default is on.
3. **Run** — Spawns `bench_apple_silicon_v2.py` (or `bench_apple_silicon_v2.py --quick`) as a child process. The button shows the assigned PID.
4. **Live logs** — After starting, click **Live Output** to open a streaming log panel that polls `/api/run-benchmark/logs` every 2 seconds.
5. **Stop** — The header badge shows a stop button while a benchmark is running. Clicking it sends `POST /api/run-benchmark/kill` to each active PID.

### Prerequisites

- **LM Studio** must be running locally with at least one model loaded (`http://127.0.0.1:1234`)
- **Python 3** with project dependencies installed (`pip install -r requirements.txt`)
- The benchmark script (`bench_apple_silicon_v2.py`) at the project root

The benchmark is spawned from the project root directory. If you run `bun run dev` from within `apps/dashboard/`, the API automatically resolves the parent project root.

---

## UI Components

| Component | File | Purpose |
|-----------|------|---------|
| `ConnectionStatusBadge` | `src/components/ConnectionStatusBadge.tsx` | Header badge — shows connected model name, provider, and hardware info |
| `BenchmarkStatusBadge` | `src/components/BenchmarkStatusBadge.tsx` | Header badge — shows running/ idle state, elapsed time, kill button, detail flyout |
| `RunBenchmarkButton` | `src/components/RunBenchmarkButton.tsx` | Toolbar button — opens benchmark launch dialog with live logs |

All three components gracefully degrade: if the API server is unreachable, they show "Disconnected" / "NODE: IDLE" with no console errors.

---

## Build & Deploy

```bash
bun run build      # Build with @astrojs/node adapter (produces dist/ + dist/server/)
bun run deploy     # Build + start Node server (node dist/server/entry.mjs)
```

The `@astrojs/node` adapter runs in `standalone` mode — the entire app (static pages + API routes) is served from a single Node.js entry point.

### Cloudflare Pages

The `cf-build` script runs `astro build` for Cloudflare Pages. Note that the API routes **will not work** on Cloudflare because they depend on Node.js `child_process`. The UI components gracefully degrade to a disconnected/idle state. If Cloudflare deployment is needed, deploy from a version before the API routes were added, or use the Node adapter on a compatible host.

---

## Results

Benchmark results are pre-generated via Python scripts:

```bash
npm run generate-real    # Generate real result fixtures
npm run generate-demo    # Generate demo data
```

Result JSON files are placed in `public/` and loaded by the dashboard at build time via `src/lib/loadResults.ts`.

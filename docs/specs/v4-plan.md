# V4 Implementation Plan — Phase 1: Foundation & Immediate Fixes

> **Status**: ✅ Complete  
> **Timeline**: Weeks 1-4  
> **Based on**: [ROADMAP.md](../../ROADMAP.md) architectural review  
> **Spec version**: 1.0.0  

---

## Overview

Phase 1 addresses the critical bottlenecks identified in the architectural review:
high-latency dashboard API calls, flat-file storage scaling limits, missing authentication,
SSE server coupling, config drift, and trace schema migration readiness.

All Phase 1 tasks are **prerequisite work** for Phase 2 (structural optimizations) and
Phase 3 (future-proofing).

---

## Task 1.1 — Dashboard Authentication

**Priority**: 🔴 Critical  
**Dependencies**: None  
**Estimated effort**: 3-4 days  

### Problem
Any network-accessible user can trigger benchmarks, view traces, and see hardware info.
No authentication on `/api/*` routes.

### Design

```
User / CI
   │
   ├── modellens auth token --ttl 5m   → JWT (short-lived)
   ├── modellens auth token --ttl 24h  → JWT (long-lived, for CI)
   │
   ▼
Dashboard API
   │
   ├── Authorization: Bearer <jwt>     → validates JWT
   └── ?token=<jwt>                     → SSE connections (EventSource can't set headers)
```

### Implementation

| Step | File | Action |
|------|------|--------|
| 1.1a | `apps/cli/commands/auth.py` (new) | `modellens auth token` — generates JWT using `MODELLENS_SECRET` env var + HS256 |
| 1.1b | `apps/dashboard/src/middleware/auth.ts` (new) | Astro middleware: validates `Bearer` token on `/api/*` routes, returns 401 if invalid |
| 1.1c | `apps/dashboard/src/pages/api/*.ts` | Apply `authMiddleware` to all API routes |
| 1.1d | `apps/dashboard/src/lib/sse.ts` | Add `?token=` query param to EventSource URLs |
| 1.1e | `packages/events/sse.py` | Accept `token` param in `worker_url` or env var; forward to bridge |
| 1.1f | `apps/dashboard/src/pages/login.astro` (new) | Simple login form; stores token in localStorage |
| 1.1g | `apps/dashboard/src/layouts/BaseLayout.astro` | Redirect to `/login` if no token in localStorage |

### Acceptance Criteria
- [ ] `curl http://localhost:4321/api/status` returns 401
- [ ] `curl -H "Authorization: Bearer <valid-token>" http://localhost:4321/api/status` returns 200
- [ ] `modellens auth token --ttl 5m` prints a valid JWT
- [ ] Dashboard login page accepts token and persists to localStorage
- [ ] SSE connections pass `?token=` and successfully connect

### Key Design Decisions
- **JWT secret**: Read from `MODELLENS_SECRET` env var; generate on first run if missing
- **No user accounts in Phase 1** — single shared secret, token-based auth only
- **Short-lived tokens by default** — 5 minutes for interactive use, 24h for CI
- **No refresh tokens** — user re-runs `modellens auth token` when expired

---

## Task 1.2 — SQLite Results Storage

**Priority**: 🔴 Critical  
**Dependencies**: None (can proceed in parallel with 1.1)  
**Estimated effort**: 4-5 days  

### Problem
Flat-file `results/` directory with JSON index — O(n) scan on every dashboard load.
At ~100 runs, latency is ~500ms; at ~1,000 runs, >5s. Cannot paginate or query efficiently.

### Design

```
results/
  runs.db                  ← SQLite database (run index + metadata)
  runs_index.json          ← (deprecated, kept for migration window)
  models/<model>/<ts>_run.json  ← (full JSON blobs retained for trace/artifact data)
  traces/*.json            ← (unchanged — large trace data stays as files)
```

### Schema

```sql
CREATE TABLE runs (
    id            TEXT PRIMARY KEY,
    model_id      TEXT NOT NULL,
    provider      TEXT NOT NULL,
    workload_type TEXT NOT NULL,   -- 'benchmark' | 'prompt_pack' | 'workload_project'
    workload_name TEXT NOT NULL,
    overall_score REAL,
    tokens_per_sec REAL,
    ttft_ms       REAL,
    memory_mb     REAL,
    status        TEXT DEFAULT 'completed',  -- 'running' | 'completed' | 'failed'
    config_json   TEXT,           -- snapshot of run config
    trace_path    TEXT,           -- relative path to trace JSON
    created_at    TEXT NOT NULL,  -- ISO 8601
    git_sha       TEXT,
    git_branch    TEXT
);

CREATE INDEX idx_runs_model ON runs(model_id);
CREATE INDEX idx_runs_created ON runs(created_at DESC);
CREATE INDEX idx_runs_score ON runs(overall_score DESC);
CREATE INDEX idx_runs_workload ON runs(workload_type, workload_name);
```

### Implementation

| Step | File | Action |
|------|------|--------|
| 1.2a | `packages/core/results_store.py` (new) | `ResultsStore` class: `insert_run(run)`, `get_runs(model?, limit?, offset?)`, `get_run(id)`, `delete_run(id)` |
| 1.2b | `scripts/migrate_to_sqlite.py` (new) | Reads `runs_index.json`, walks `results/models/`, inserts into SQLite. Dry-run mode with diff output |
| 1.2c | `apps/cli/modellens.py` | `modellens migrate sqlite` subcommand |
| 1.2d | `apps/dashboard/src/lib/loadResults.ts` | Replace `readFileSync` + `JSON.parse` with `better-sqlite3` queries |
| 1.2e | `apps/dashboard/src/pages/api/traces/index.ts` | Query `runs.db` instead of scanning filesystem |
| 1.2f | `apps/dashboard/src/pages/api/status.ts` | Query `runs.db` for latest runs + aggregate stats |
| 1.2g | `apps/cli/results_schema.py` | Add `save_to_db()` method to `ResultsCollector` |
| 1.2h | `apps/cli/run_manifest.py` | Write to SQLite on run completion |

### Acceptance Criteria
- [ ] `modellens migrate sqlite` successfully migrates existing `results/` data
- [ ] `modellens migrate sqlite --dry-run` prints diff without writing
- [ ] Dashboard `/api/traces?limit=20` returns in <50ms (vs current 500ms+)
- [ ] Dashboard `/api/status` returns in <50ms
- [ ] New benchmark runs automatically write to SQLite
- [ ] Existing JSON files are preserved (non-destructive migration)

### Key Design Decisions
- **`better-sqlite3` in Node.js** (synchronous, fast, embedded) — matches Python's `sqlite3` stdlib
- **Full traces stay as JSON files** — SQLite stores metadata + path pointer only
- **WAL mode** enabled for concurrent reads during writes
- **No ORM** — raw SQL for transparency and performance

---

## Task 1.3 — Decouple SSE Server from CLI

**Priority**: 🟡 High  
**Dependencies**: None (Cloudflare Worker already done)  
**Estimated effort**: 2-3 days  
**Status**: Partially complete

### What's Done
- ✅ Cloudflare Worker SSE Bridge (`apps/sse-bridge/`) with Durable Objects
- ✅ `EventBusSSEServer._forward_to_worker()` — forwards events to bridge via thread pool
- ✅ E2E test validates end-to-end: local event → bridge → SSE stream → dashboard
- ✅ URL construction: query params/fragments stripped via `urlparse`

### What's Left

| Step | File | Action |
|------|------|--------|
| 1.3a | `apps/cli/commands/sse.py` (new) | `modellens sse serve --port 9090` standalone command |
| 1.3b | `packages/events/sse.py` | Refactor `EventBusSSEServer` to accept `subscribe_existing=False` param (for standalone mode) |
| 1.3c | `apps/dashboard/src/lib/useEventStream.ts` | Auto-detect: try `ws://localhost:9090/events` first, then `BRIDGE_URL/events` |
| 1.3d | `apps/dashboard/src/lib/useEventStream.ts` | Add `?token=` param support (from 1.1) |

### Acceptance Criteria
- [ ] `modellens sse serve --port 9090` starts a standalone SSE relay
- [ ] Dashboard connects to standalone SSE when available, falls back to Cloudflare bridge
- [ ] SSE server survives benchmark process restart
- [ ] Multiple dashboard clients can connect simultaneously

---

## Task 1.4 — Cache Hardware Detection in Dashboard

**Priority**: 🟡 High  
**Dependencies**: 1.3 (for standalone SSE)  
**Estimated effort**: 1 day  

### Problem
`/api/status` spawns `python3 -c "..."` per request — 2-5s latency, brittle path resolution.

### Implementation

| Step | File | Action |
|------|------|--------|
| 1.4a | `apps/dashboard/src/pages/api/status.ts` | Cache hardware result in-memory with 60s TTL |
| 1.4b | `apps/dashboard/src/pages/api/status.ts` | If cache miss + Python unavailable, use `systeminformation` npm as fallback |
| 1.4c | `packages/core/hardware.py` | Add `--json` flag for machine-parseable output |
| 1.4d | `apps/dashboard/src/components/ServerUptimeBadge.tsx` | Show cache freshness indicator |

### Acceptance Criteria
- [ ] `/api/status` returns in <100ms (cached)
- [ ] Cache auto-refreshes every 60s
- [ ] Falls back to `systeminformation` if Python not available

---

## Task 1.5 — Trace Schema Versioning + Migration

**Priority**: 🟡 High  
**Dependencies**: 1.2 (for SQLite migration infrastructure)  
**Estimated effort**: 2 days  

### Design

```python
@dataclass
class Trace:
    version: str = "1.0.0"  # NEW: schema version
    trace_id: str
    events: List[TraceEvent]
    metrics: TraceMetrics
    # ...
```

Migration functions:
```python
def migrate_trace(trace: dict) -> dict:
    """Migrate a trace dict from its current version to latest."""
    version = trace.get("version", "1.0.0")
    if version == "1.0.0":
        return trace  # current version
    # Future migrations:
    # if version == "0.9.0":
    #     trace = migrate_0_9_to_1_0(trace)
    return trace
```

### Implementation

| Step | File | Action |
|------|------|--------|
| 1.5a | `packages/core/trace_schema.py` | Add `version: str = "1.0.0"` to `Trace` dataclass |
| 1.5b | `packages/core/trace_schema.py` | Add `migrate_trace(trace: dict) -> dict` function |
| 1.5c | `scripts/migrate_traces.py` (new) | Batch migration: scans `results/traces/`, migrates each file |
| 1.5d | `apps/dashboard/src/lib/traceTypes.ts` | Add `version` field to TypeScript `Trace` interface |
| 1.5e | `apps/dashboard/src/lib/loadTraces.ts` | Migrate on read if version mismatch |

### Acceptance Criteria
- [ ] `Trace.to_dict()` includes `"version": "1.0.0"`
- [ ] `migrate_trace({"trace_id": "x"})` returns `{"version": "1.0.0", "trace_id": "x"}`
- [ ] `scripts/migrate_traces.py` updates all files in `results/traces/`
- [ ] Dashboard handles both v1.0.0 and future v1.1.0 traces

---

## Task 1.6 — Unified Config Validation

**Priority**: 🟢 Medium  
**Dependencies**: None  
**Estimated effort**: 2-3 days  

### Problem
Two config systems: `config.yaml` (general benchmarks, nested YAML) and `config.json` (devbench, flat JSON). Different schemas, different validation, duplicated logic.

### Design

Use a **single `config_schema.json`** (JSON Schema draft-07) that validates both config files. The `config_manager.py` handles loading, merging, and validating against the unified schema.

```yaml
# config.yaml (reorganized)
version: "2.0.0"

general:       # ← was top-level benchmarks
  samples_per_benchmark: 100
  benchmarks:
    mmlu_pro: { enabled: true, ... }

devbench:      # ← was config.json
  models: { auto_detect: true }
  evaluation: { runs_per_prompt: 5 }
  ...

output:
  directory: "results"
  formats: [json, csv, html]
```

### Implementation

| Step | File | Action |
|------|------|--------|
| 1.6a | `apps/cli/config_schema.json` | Rewrite as unified schema covering both `general:` and `devbench:` sections |
| 1.6b | `apps/cli/config_manager.py` | Load YAML (with `!include` support); validate both sections against unified schema |
| 1.6c | `apps/cli/config.yaml` | Reorganize under `general:` and `devbench:` top-level keys |
| 1.6d | `apps/cli/config.json` | Add `"$ref": "config.yaml#/devbench"` or remove entirely (deprecated) |
| 1.6e | `apps/cli/benchmark.py` | Read from `config["general"]` instead of direct YAML |
| 1.6f | `apps/cli/bench_apple_silicon_v2.py` | Read from `config["devbench"]` instead of JSON file |

### Acceptance Criteria
- [ ] `ConfigManager` validates both `general:` and `devbench:` sections
- [ ] General benchmarks run using `config.yaml` only (no JSON needed)
- [ ] DevBench v2 runs using `config.yaml` only (no JSON needed)
- [ ] `config.json` is deprecated with warning on load

---

## Task 1.7 — Provider Plugin Registration

**Priority**: 🟢 Medium  
**Dependencies**: 1.6 (for unified config)  
**Estimated effort**: 1-2 days  

### Problem
Adding a new provider requires edits in 3+ files (`PROVIDER_CONFIG` in utils.py, `_resolve_provider` in modellens.py, providers `__init__.py`). No auto-discovery.

### Design

Use Python **entry points** (`pyproject.toml`):

```toml
[project.entry-points."modellens.providers"]
lm-studio = "providers.openai_compatible:OpenAICompatibleProvider"
ollama = "providers.ollama:OllamaClient"
jan = "providers.jan:JanClient"
```

Auto-discovery:
```python
def discover_providers() -> dict[str, ProviderAdapter]:
    """Discover all registered providers via entry points."""
    from importlib.metadata import entry_points
    providers = {}
    for ep in entry_points(group="modellens.providers"):
        cls = ep.load()
        providers[ep.name] = cls()
    return providers
```

### Implementation

| Step | File | Action |
|------|------|--------|
| 1.7a | `pyproject.toml` | Add `[project.entry-points."modellens.providers"]` with all 6 providers |
| 1.7b | `packages/providers/__init__.py` | Add `discover_providers()` and `get_provider(name)` |
| 1.7c | `apps/cli/commands/utils.py` | Replace hardcoded `PROVIDER_CONFIG` with `discover_providers()` |
| 1.7d | `apps/cli/modellens.py` | Replace `_resolve_provider` probes with `discover_providers()` |
| 1.7e | `apps/cli/commands/info.py` | Use `discover_providers()` for `modellens info` |

### Acceptance Criteria
- [ ] `modellens info` lists all providers from entry points
- [ ] `modellens run --provider ollama` works without hardcoded config
- [ ] Third-party providers can register via `pip install my-provider` + entry point
- [ ] Auto-detection probes are provided by each provider class (not hardcoded)

---

## Task 1.8 — Test Stability

**Priority**: 🟢 Medium  
**Dependencies**: None  
**Estimated effort**: 1 day  

### Problem
`test_provider_clients.py` uses `patch("providers.openai_compatible.OpenAI")` which patches the wrong location (patches where defined, not where imported). Tests fail intermittently.

### Implementation

| Step | File | Action |
|------|------|--------|
| 1.8a | `tests/test_provider_clients.py` | Fix all `@patch` targets to patch where imported (`packages.providers.X.OpenAI`) |
| 1.8b | `tests/test_provider_integration.py` | Add `@pytest.mark.skipif` for tests requiring live providers |
| 1.8c | `.github/workflows/ci.yml` | Add `pytest -x --tb=short tests/` step (already done) |
| 1.8d | `pyproject.toml` | Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and timeout |

### Acceptance Criteria
- [ ] All tests pass 10 consecutive runs without failure
- [ ] `pytest tests/` completes in <30s
- [ ] CI `Run Python tests` job passes consistently

---

## Phase 1 Completion Checklist

- [x] 1.1 — Dashboard authentication (JWT)
- [x] 1.2 — SQLite results storage
- [x] 1.3 — Decouple SSE server (standalone)
- [x] 1.4 — Cache hardware detection
- [x] 1.5 — Trace schema versioning
- [x] 1.6 — Unified config validation
- [x] 1.7 — Provider plugin registration
- [x] 1.8 — Test stability

---

## Risk Mitigation

| Risk | Task | Mitigation |
|------|------|------------|
| SQLite migration corrupts data | 1.2 | Dry-run mode, parallel `results_v2/`, CI validation |
| SSE decoupling breaks dashboard | 1.3 | Both embedded + standalone run in parallel for 1 release |
| Auth breaks CLI→dashboard flow | 1.1 | Short-lived JWTs, `?token=` for SSE, `MODELLENS_DASHBOARD_TOKEN` env var |
| Unified config breaks devbench | 1.6 | Keep `config.json` as deprecated fallback; YAML migration helper |

---

## Files Created (Phase 1)

| File | Task | Purpose |
|------|------|---------|
| `apps/cli/commands/auth.py` | 1.1 | JWT token generation |
| `apps/dashboard/src/middleware/auth.ts` | 1.1 | Astro auth middleware |
| `apps/dashboard/src/pages/login.astro` | 1.1 | Login page |
| `packages/core/results_store.py` | 1.2 | SQLite results store |
| `scripts/migrate_to_sqlite.py` | 1.2 | Flat-file → SQLite migration |
| `apps/cli/commands/sse.py` | 1.3 | Standalone SSE server command |
| `scripts/migrate_traces.py` | 1.5 | Trace schema migration |
| `docs/specs/v4-plan.md` | — | This file |

---

*Last updated: 2026-06-04 — Phase 1 complete*

# Model Lens Roadmap

## Vision

Become the standard observability layer for local LLMs.
See [VISION.md](VISION.md) for the full philosophy.

---

## V1 — Replace ad-hoc benchmarking

Status: **Complete**

- [x] LM Studio provider
- [x] Ollama provider
- [x] Unified `modellens` CLI (`run`, `info`, `leaderboard`, `models`)
- [x] Unified benchmark harness (MMLU-Pro, GSM8K, HumanEval, etc.)
- [x] DevBench v2 (TypeScript/NestJS/React, statistical rigor)
- [x] Benchmark dashboard (Astro + React)
- [x] Prompt packs (React, NestJS, debugging, agentic)
- [x] Prompt generation (paraphrasing, variable substitution, contextual mutation)
- [x] Hardware detection (CPU, GPU, RAM, OS, architecture)
- [x] Cloudflare Pages deployment
- [x] Community leaderboard

---

## V2 — Local model observability platform

Status: **In Progress** (core event infrastructure done, visualization in progress)

- [x] Execution trace capture (prompt, response, token stream, latency, errors)
- [x] Trace replay with playback controls (play, pause, speed, step)
- [ ] Side-by-side model comparison (token stream, latency diff, memory diff)
- [ ] Snapshot system (save/share execution state via URL)
- [x] Workload evaluation (real projects: React, NestJS, Rust, Python)

---

## V3 — Local AI observability platform

Status: **In Progress** (providers expanded, skills foundation laid)

- [ ] Regression detection between model versions
- [x] Skill system (extensible benchmark logic — types, registry, lockfile, builtins)
- [ ] WASM sandbox for skills
- [x] MCP server integration (bridge foundation)
- [x] Provider expansion (Open WebUI, Jan, llama.cpp, vLLM — all 6 implemented)

---

## Supported Providers

| Phase | Providers |
|-------|-----------|
| **Phase 1 ✅** | LM Studio, Ollama |
| **Phase 2 ✅** | Open WebUI, Jan, llama.cpp, vLLM |
| **Phase 3 ✅** | OpenAI-compatible generic layer |
| **Phase 4** | LocalAI, KoboldCPP, Text Generation WebUI |

---

## Success Criteria

### V1 ✅
- Benchmark LM Studio models ✅
- Benchmark Ollama models ✅
- Publish Cloudflare Pages report ✅
- Prompt packs ✅
- Leaderboard ✅

### V2 🚧
- Trace capture ✅
- Replay ✅
- SSE streaming ✅
- Event bus ✅
- Side-by-side comparison
- Snapshots
- Trace diffing
- Historical comparisons

### V3 🚧
- Skill system (types, registry, lockfile) ✅
- Provider expansion (6 providers) ✅
- MCP bridge ✅
- SSE Bridge Worker (Cloudflare Durable Objects) ✅
- SSE forwarding (ThreadPoolExecutor, User-Agent, URL edge cases) ✅
- WASM sandbox
- Workload evaluation ✅
- Regression detection

### V4 🚧 (Phase 1: Foundation & Immediate Fixes)
- Dashboard authentication
- SQLite results storage
- Standalone SSE server
- Cached hardware detection
- Trace schema versioning
- Unified config validation
- Provider plugin registration
- Test stability

---

## Current State

Status: **Alpha**

Model Lens now includes:

- Benchmarking (MMLU-Pro, GSM8K, HumanEval, etc.)
- Trace capture
- Replay viewer (SSE streaming, event replay to disk)
- Workload evaluation
- Multi-provider support (LM Studio, Ollama, Open WebUI, Jan, llama.cpp, vLLM)
- Dashboard infrastructure
- Event bus (TokenGenerated, CompletionEvent, MetricEvent, ErrorEvent, RunLifecycleEvent)
- CI enforcement (ruff lint, ruff format, mypy, pytest)
- Pre-commit hooks

### V1 — Benchmark Foundation 💚 Complete

- LM Studio
- Ollama
- Benchmark suite
- Dashboard
- Prompt packs
- Community leaderboard

### V2 — Observability Foundation 🚧 In Progress

- [x] Event system — EventBus wired into provider + benchmark flow
- [x] SSE streaming — real-time dashboard event bridge
- [x] Replay infrastructure — `EventBusReplayWriter` persists events to disk
- [x] Trace capture — token-level execution timeline
- [x] Timeline visualization — TraceTimeline component in dashboard
- [x] Provider abstraction — `ProviderAdapter` with 6 implementations
- [ ] Snapshot export
- [ ] Shareable replay links
- [ ] Trace diffing
- [ ] Historical comparisons

### V3 — Developer Observability 🚧 In Progress

- [x] Open WebUI
- [x] Jan
- [x] llama.cpp
- [x] vLLM
- [x] MCP bridge foundation
- [x] OpenAI-compatible provider layer
- [x] SSE Bridge Worker — Cloudflare Durable Objects for production SSE
- [x] SSE forwarding — ThreadPoolExecutor, User-Agent, URL edge cases
- [x] E2E SSE bridge tests (unit + live integration)
- [ ] Regression detection
- [ ] Skills runtime
- [ ] Skill registry
- [ ] WASM isolation
- [ ] MCP server mode

### V4 — Foundation & Structural Optimization 🚧 In Progress

See [docs/specs/v4-plan.md](docs/specs/v4-plan.md) for detailed implementation plan.

- [ ] Dashboard authentication (JWT)
- [ ] SQLite results storage (replaces flat-file `runs_index.json`)
- [ ] Standalone SSE server (`modellens sse serve`)
- [ ] Cached hardware detection in dashboard
- [ ] Trace schema versioning + migration
- [ ] Unified config validation (YAML + JSON → single schema)
- [ ] Provider plugin registration (entry points)
- [ ] Test stability fixes

---

# Architectural Review & Next-Version Roadmap

*Generated: 2026-06-04 | Reviewer: Principal Software Architect*

---

## 1. ARCHITECTURAL HEALTH CHECK

### ✅ What Is Built Well

| Area | Assessment | Evidence |
|------|------------|----------|
| **Event-driven core** | Excellent | `EventBus` is thread-safe, typed, self-contained; clean pub/sub with sync/async handlers, priority, run-scoped subscriptions, publish context |
| **Provider abstraction** | Strong | `ProviderAdapter` ABC with 6 implementations; URL utilities (`normalize_base_url`, `get_root_url`, `url_join`) eliminate string-concat bugs; all providers emit events via `OpenAICompatibleProvider` |
| **Dual benchmark systems** | Intentional & correct | General suite (`BenchmarkSuite` + 11 benchmarks) and DevBench v2 (`AppleSiliconBenchmarkV2`) coexist as first-class; shared scoring/eval modules; config separation (YAML vs JSON) |
| **Trace capture** | Production-grade | `TraceCapture` context manager with token-level timing, inter-token gaps, TTFT, memory pressure; serializes to dashboard-compatible JSON |
| **Replay infrastructure** | Solid | `EventBusReplayWriter` persists all events per `run_id`; atomic writes; index file; standalone runner |
| **SSE streaming** | Well-engineered | `EventBusSSEServer` in daemon thread; connection management; Cloudflare Worker forwarder via thread pool (not per-event threads) |
| **Package boundaries** | Enforced | `events/` self-contained; `providers/` depend only on `events` + `base.py`; `core/` depends on `providers`; `benchmarks/` import from `core`; `skills/` self-contained |
| **Quality gates** | Strict | CI: ruff lint, ruff format, mypy, pytest — all strict; pre-commit mirrors CI |
| **Observability-first DNA** | Clear | Every provider call emits `TokenGeneratedEvent` × N + `CompletionEvent`; benchmarks emit `RunLifecycleEvent` + `MetricEvent`; no `print()` for observability data |

### ⚠️ Architectural Debt & Anti-Patterns

| Issue | Severity | Location | Impact |
|-------|----------|----------|--------|
| **No persistent storage layer** | High | `results/` flat JSON files | Dashboard loads all runs into memory; no query/index; O(n) scans; will not scale past ~500 runs |
| **SSE server single-process** | Medium | `EventBusSSEServer` in benchmark process | Cannot scale horizontally; dashboard tied to CLI process lifecycle; no multi-user support |
| **Event bus = global singleton** | Medium | `default_bus` module-level | Test isolation requires manual `clear()`; no per-request scoping in dashboard API routes |
| **Dashboard API spawns Python subprocess** | High | `apps/dashboard/src/pages/api/status.ts:34-58` | Spawns `python3 -c "..."` per request; 2-5s latency; no connection pooling; brittle path resolution |
| **No authentication/authorization** | High | Entire dashboard | Anyone with network access can trigger benchmarks, view traces, see hardware info |
| **Config drift: YAML vs JSON** | Medium | `config.yaml` (general) vs `config.json` (devbench) | Different schemas, different validation; duplication in CLI commands |
| **Hardcoded provider defaults** | Low | `PROVIDER_CONFIG` in `commands/utils.py` | Adding provider requires edits in 3+ files; no plugin mechanism |
| **Trace schema v1.0.0 — no migration path** | Medium | `docs/specs/run-schema.md` | Breaking changes to `Trace`/`Run` will corrupt historical data |
| **Skills system incomplete** | Medium | `packages/skills/` | Types/registry/lockfile exist but no runtime executor, no WASM sandbox, no MCP server mode |
| **No structured metrics backend** | Medium | Events → JSON files only | No time-series DB; no aggregation; no alerting; dashboard computes on-load |

---

## 2. CRITICAL BOTTLENECK IDENTIFICATION

### #1: Flat-File Results Storage — O(n) Dashboard Load
**Current**: `results/models/<model>/<timestamp>_run.json` + `results/traces/*.json` + `results/replays/*.json` + `runs_index.json`
**Failure mode**: At ~1,000 runs, dashboard `/api/traces` and `/api/status` take >5s; memory spikes; index rebuild on every write
**Root cause**: No database; JSON parsed on every request; no pagination at storage layer
**Fix**: SQLite (or DuckDB) for run index + trace metadata; keep full traces as JSON blobs or Parquet

### #2: SSE Server Coupled to Benchmark Process
**Current**: `EventBusSSEServer` starts in CLI process (`_run_general_framework`, `workload run`)
**Failure mode**: Dashboard loses stream if CLI crashes; cannot serve multiple concurrent users; no horizontal scaling; Cloudflare Worker forwarder is best-effort fire-and-forget
**Root cause**: SSE server embedded in benchmark runner instead of standalone service
**Fix**: Decouple SSE into independent service (Cloudflare Worker + Durable Objects or separate Python process) that subscribes to a message bus (Redis Streams, NATS, or SQLite-based event log)

### #3: Dashboard API Spawns Python Subprocess Per Request
**Current**: `status.ts` spawns `python3 -c "import sys; sys.path...; from core.hardware import detect_hardware"` per HTTP request
**Failure mode**: 2-5s latency per `/api/status` call; fails if Python env differs; no caching; blocks Node event loop
**Root cause**: Hardware detection lives in Python; dashboard is TypeScript; no shared library or RPC
**Fix**: Expose hardware detection via HTTP endpoint from a long-running Python service, or port `detect_hardware` to TypeScript (using `systeminformation` npm), or cache result with TTL

---

## 3. NEXT VERSION ROADMAP (PHASED TIMELINE)

### Phase 1: Foundation & Immediate Fixes (Weeks 1-4)
*Low-hanging fruit, critical security/debt fixes, unblocking work*

| # | Task | Owner | Dependencies | Acceptance Criteria |
|---|------|-------|--------------|---------------------|
| 1.1 | **Add authentication to dashboard** | Backend | — | All `/api/*` routes require Bearer token; `modellens` CLI issues short-lived tokens; dashboard login page |
| 1.2 | **Replace flat-file index with SQLite** | Backend | — | `runs_index.json` → `results/runs.db` (SQLite); `/api/traces`, `/api/status` query DB; migration script for existing data |
| 1.3 | **Decouple SSE server from CLI** | Backend | 1.2 | Standalone `modellens-sse` command; subscribes to event log (SQLite or Redis); dashboard connects to fixed URL |
| 1.4 | **Cache hardware detection in dashboard** | Frontend | 1.3 | `/api/status` returns cached hardware (<100ms); TTL 60s; background refresh |
| 1.5 | **Add trace schema versioning + migration** | Backend | 1.2 | `Trace.version` field; migration script `scripts/migrate_traces.py`; dashboard handles v1+v2 |
| 1.6 | **Unify config validation (YAML + JSON → single schema)** | CLI | — | `config_schema.json` (JSON Schema) validates both; `config_manager.py` loads/merges/validates; deprecate raw YAML/JSON access |
| 1.7 | **Provider plugin registration (remove hardcoded `PROVIDER_CONFIG`)** | Providers | — | Entry-point based (`modellens.providers`); auto-discovery; single `add_provider()` call |
| 1.8 | **Fix test flakiness: `test_provider_clients.py` patch targets** | QA | — | All tests pass 10x in a row; no `patch("providers.openai_compatible.OpenAI")` — patch where imported |

### Phase 2: Structural Optimizations (Weeks 5-10)
*Database adjustments, caching, architectural decoupling, observability depth*

| # | Task | Owner | Dependencies | Acceptance Criteria |
|---|------|-------|--------------|---------------------|
| 2.1 | **Time-series metrics backend (DuckDB or SQLite + hyperfunctions)** | Backend | 1.2 | `MetricEvent` → DuckDB; `/api/metrics?model=X&metric=tokens_per_second` returns aggregated series; <50ms p99 |
| 2.2 | **Trace diffing engine (side-by-side comparison)** | Core | 1.5 | `diff_traces(trace_a, trace_b)` → token-level diff (insert/delete/replace), latency delta, memory delta; dashboard Compare page |
| 2.3 | **Snapshot export + shareable URLs** | Core | 1.5 | `Trace.to_snapshot()` → compressed JSON + base64 URL param; `/snapshots/[id]` loads snapshot; no server state |
| 2.4 | **Historical regression detection** | Core | 2.1 | `detect_regression(model, metric, window=10)` → statistical change-point detection (CUSUM/Page-Hinkley); alert event |
| 2.5 | **Skills runtime executor (no WASM yet)** | Skills | — | `SkillRunner.execute(skill_name, input)` → runs built-in skills (json_parse, diff, read_file, write_file); emits `ToolCallEvent` |
| 2.6 | **MCP server mode (stdio + SSE)** | Providers | 1.3 | `modellens mcp serve` → exposes `list_models`, `run_prompt`, `chat_completion` as MCP tools; dashboard can connect |
| 2.7 | **Benchmark result caching (avoid re-running identical configs)** | CLI | 1.6 | Content-addressable cache keyed by `(model, provider, benchmark_config_hash)`; `--force` to bypass |
| 2.8 | **Structured logging → OpenTelemetry collector** | Observability | — | `packages/logging.py` exports OTLP; `OTEL_EXPORTER_OTLP_ENDPOINT` env var; traces appear in Jaeger/Grafana |

### Phase 3: Future-Proofing & Scalability (Weeks 11-20)
*Advanced patterns, CI/CD enhancements, monitoring, ecosystem*

| # | Task | Owner | Dependencies | Acceptance Criteria |
|---|------|-------|--------------|---------------------|
| 3.1 | **WASM sandbox for skills (wasmtime / wasmer)** | Skills | 2.5 | Untrusted skill code executes in isolated WASM module; memory/CPU limits; no host access |
| 3.2 | **VS Code extension (trace viewer + run trigger)** | Frontend | 2.3 | `Model Lens: Open Trace` command; sidebar shows recent runs; click → opens trace timeline in editor |
| 3.3 | **OpenTelemetry trace export (standardize `Trace` → OTLP)** | Observability | 2.8 | `Trace.to_otlp()` → spans with attributes; `modellens run --otel-endpoint`; compatible with Grafana Tempo |
| 3.4 | **Multi-user dashboard with workspaces** | Frontend | 1.1 | User accounts; workspaces (team/shared); RBAC (viewer/editor/admin); audit log |
| 3.5 | **Distributed agent traces (multi-step workflows)** | Core | 3.1 | `Trace` supports parent/child spans; skill tool calls appear as child spans; waterfall view |
| 3.6 | **CI/CD: benchmark regression gate in PR checks** | CI | 2.4 | `modellens run --ci --compare-baseline main` → fails PR if `tokens_per_second` drops >10% or accuracy drops >5% |
| 3.7 | **Provider health monitoring + alerting** | Observability | 2.1 | Background job polls providers; emits `ErrorEvent` on degradation; webhook/email integration |
| 3.8 | **Community prompt pack registry (GitHub-backed)** | Ecosystem | — | `modellens pack publish` → GitHub Release; `modellens pack install owner/repo`; versioned, signed |

---

## 4. IMPLEMENTATION RISK ASSESSMENT

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Migration from flat files to SQLite corrupts historical runs** | Medium | High | • Write migration script `scripts/migrate_to_sqlite.py` with dry-run mode<br>• Keep `results/` read-only during migration; write to `results_v2/`<br>• Validate row counts + checksums post-migration<br>• Run migration in CI on sample dataset before merge |
| **Decoupling SSE server breaks real-time dashboard for existing users** | High | Medium | • Phase 1.3: Run both embedded + standalone SSE in parallel for 1 release<br>• Feature flag `MODELLENS_SSE_MODE=embedded|standalone`<br>• Dashboard auto-detects: tries `ws://localhost:9090` then falls back to embedded |
| **Authentication breaks CLI → dashboard integration** | Medium | High | • CLI issues short-lived JWT (`modellens auth token --ttl 5m`)<br>• Dashboard accepts token via `?token=` query param for SSE connections<br>• Document `MODELLENS_DASHBOARD_TOKEN` env var for headless CI |
| **WASM sandbox adds significant binary size / build complexity** | Medium | Medium | • Use `wasmtime-py` (pure Python, ~5MB) not `wasmer` (native)<br>• Optional dependency: `pip install "modellens[wasm]"`<br>• Fallback: if WASM unavailable, run skills in-process with `ResourceWarning` |
| **OpenTelemetry export requires trace schema changes (breaking v1.0.0)** | Low | High | • Phase 1.5 adds `Trace.version` + migration<br>• OTLP export is additive: `Trace.to_otlp()` reads v1/v2, emits standard spans<br>• No change to on-disk format; only new export path |

---

## Appendix: Quick Reference

### Key Files to Touch First

| Phase | Files |
|-------|-------|
| 1.1 | `apps/dashboard/src/middleware/auth.ts` (new), `apps/dashboard/src/pages/api/*.ts` |
| 1.2 | `packages/core/results_store.py` (new), `scripts/migrate_to_sqlite.py` (new), `apps/dashboard/src/lib/loadResults.ts` |
| 1.3 | `apps/cli/commands/sse.py` (new), `packages/events/sse.py` (refactor), `apps/dashboard/src/lib/sse.ts` |
| 1.5 | `packages/core/trace_schema.py` (add `version`), `scripts/migrate_traces.py` (new) |
| 1.6 | `apps/cli/config_manager.py`, `apps/cli/config_schema.json` (new) |
| 1.7 | `packages/providers/__init__.py` (entry points), `apps/cli/commands/utils.py` |
| 2.1 | `packages/core/metrics_store.py` (new, DuckDB), `apps/dashboard/src/pages/api/metrics.ts` (new) |
| 2.2 | `packages/core/trace_diff.py` (new), `apps/dashboard/src/components/TraceComparison.tsx` |
| 2.3 | `packages/core/trace_schema.py` (add `to_snapshot`), `apps/dashboard/src/lib/loadSnapshots.ts` |
| 2.5 | `packages/skills/runner.py` (new), `packages/skills/builtins/` |

### Commands to Add

```bash
# Phase 1
modellens auth token --ttl 5m           # Issue dashboard JWT
modellens migrate sqlite                # Flat-file → SQLite
modellens sse serve --port 9090         # Standalone SSE server

# Phase 2
modellens trace diff <trace_a> <trace_b>  # Side-by-side diff
modellens trace snapshot <trace_id>       # Export shareable URL
modellens mcp serve                       # MCP server (stdio/SSE)
modellens skill run <name> --input '{}'   # Execute skill

# Phase 3
modellens pack publish                    # Publish prompt pack to GitHub
modellens pack install owner/repo@v1.2.0  # Install community pack
modellens vscode install                  # Install VS Code extension
```

---

*This roadmap is a living document. Update on every major architectural decision.*
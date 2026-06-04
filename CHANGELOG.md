# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project follows [Semantic Versioning](https://semver.org/) where practical.

---

## Unreleased

### Added

#### Observability & Trace System

- Execution trace capture system (token-level + event-level observability)
- Event bus wired into provider and benchmark flow: `TokenGeneratedEvent`, `CompletionEvent`, `MetricEvent`, `ErrorEvent`, `RunLifecycleEvent` emitted throughout the entire pipeline
- Thread-safe `EventBus` with `threading.Lock` for concurrent benchmark execution
- SSE bridge auto-started by CLI for real-time dashboard streaming (`--sse-port N`)
- EventBus replay writer persists all events to disk for historical replay
- Trace replay engine (play / pause / step / time-scale controls)
- Unified trace schema (`Trace`, `TraceEvent`, `TraceMetrics`)
- Cross-provider instrumentation via event bus

#### Developer Tooling

- Pre-commit hook config (`.pre-commit-config.yaml`): ruff lint, ruff format, mypy, file hygiene
- CI enforcement: `ruff check`, `ruff format --check`, `mypy`, and strict `pytest` on every push (`.github/workflows/ci.yml`)
- Dev dependencies in `pyproject.toml` (`ruff`, `mypy`, `pytest`, `pytest-cov`)
- Structured logging module (`packages/logging.py`) with Rich console and file output — `print()` calls replaced across providers, core, events, and CLI
- URL utility helpers in `packages/providers/base.py`: `normalize_base_url()`, `get_root_url()`, `url_join()` — replaces fragile `.rstrip()` / `.removesuffix()` across all providers and CLI commands
- Python packaging support via `pyproject.toml`

#### Hybrid Benchmark System

- Dual benchmark architecture (both systems first-class and equally authoritative):
  - General `BenchmarkSuite` (`packages/core/benchmark.py`)
  - Apple Silicon / DevBench v2 (`apps/cli/bench_apple_silicon_v2.py`)
- Shared scoring + evaluation modules across both systems
- Unified provider abstraction layer for both pipelines
- Config separation: `config.yaml` (general benchmarks) and `config.json` (DevBench / Apple Silicon workloads)
- `LMStudioClient` deprecated — now a thin wrapper around `OpenAICompatibleProvider`; `BenchmarkSuite` now accepts `ProviderAdapter` directly

#### Provider Layer Expansion

- OpenAI-compatible unified provider interface (`/v1/chat/completions`)
- Added / standardized providers:
  - Ollama (`packages/providers/ollama.py`)
  - llama.cpp
  - vLLM
  - Open WebUI
  - Jan
  - LM Studio (OpenAI-compatible base path)
- Auto-detection pipeline: LM Studio → Ollama → llama.cpp → vLLM → Open WebUI → Jan
- OpenBench integration bridge
- LM Eval integration bridge
- MCP bridge enhancements
- Shared provider dataclasses and adapter interfaces

#### Workload Evaluation System

- Real-project workload engine:
  - `ProjectLoader`
  - `TaskGenerator`
  - `WorkloadRunner`
  - `WorkloadScorer` (multi-axis scoring)
- Supports real-world codebases (React / NestJS / Python / Rust)

#### Skills System (V3 foundation)

- Extensible skill runtime system
- Lockfile-validated skill registry (`modellens.lock`)
- Built-in deterministic skills: JSON parsing, diff generation, file read / write abstraction layer

#### Prompt System

- Prompt packs system (versioned benchmark suites)
- Context-aware prompt mutation engine
- Prompt generator improvements: whole-word boundary protection (`re.sub` migration), anti-corruption safeguards for framework tokens
- Packs: React, NestJS, Debugging, Agentic coding

#### CLI (Unified `modellens` interface)

- Unified CLI entrypoint: `apps/cli/modellens.py`
- Commands: `run`, `info`, `leaderboard`, `models`, `workload run`, `compare`
- Provider auto-detection from CLI layer
- Run manifest system for reproducibility

#### Dashboard (Astro + React)

- Full observability UI: trace replay timeline, model comparison views, benchmark history, workload results explorer
- SSE-based live updates
- Cloudflare Pages deployment support
- Node adapter (`@astrojs/node`) for API routes
- Custom font assets, error boundary component
- Dashboard deployment script (`deploy.sh`)

#### Hardware Intelligence

- Cross-platform hardware detection: CPU / GPU / RAM
- Apple Silicon optimization layer
- Memory and latency profiling per run

#### Community & Distribution

- Community leaderboard publishing
- Dashboard status and benchmark APIs
- Health monitoring endpoints
- Wrangler configuration improvements

#### Trace Diffing Engine

- `packages/core/trace_diff.py` — three-level diff engine: step alignment (timing/type/status), token-level text diff (`difflib.SequenceMatcher`), metric/artifact deltas
- `apps/cli/commands/trace.py` — `modellens trace diff` and `trace text-diff` CLI commands with `--json` output
- `apps/dashboard/src/pages/api/traces/diff.ts` — `/api/traces/diff` endpoint (shell-injection-safe via regex validation + `spawnSync` args)
- `apps/dashboard/src/lib/traceDiff.ts` — TypeScript types + `computeTraceDiff()` client-side fallback

#### Snapshot Export & Shareable URLs

- `Trace.to_snapshot()`, `to_snapshot_json()`, `to_snapshot_base64()` with compressed text fields and proper hashing
- `snapshot_from_base64()` / `snapshot_to_share_url()` for no-server-state sharing via `/runs?snap=BASE64`
- `modellens trace snapshot <trace_id>` CLI with `--base64` and `--url` flags
- `apps/dashboard/src/pages/runs/[...id].astro` — individual snapshot viewer supporting both server-side and base64-query sharing
- `apps/dashboard/src/lib/loadSnapshots.ts` — `snapshotFromQuery()` / `snapshotToQuery()` for base64 query params

#### Skills Runtime Executor

- `packages/skills/runner.py` — `SkillRunner` class with `execute()` / `execute_sync()` for single skill runs, `execute_batch()` / `execute_batch_sync()` for sequential batch execution
- Input validation against skill schema, ToolCallEvent emission to EventBus
- `modellens skill list`, `skill info <name>`, `skill run <name> '<json>'`, `skill run --batch` CLI commands

#### MCP Server Mode

- `packages/providers/mcp/server.py` — Full MCP server with JSON-RPC 2.0 protocol: `MCPServerStdio` (stdin/stdout transport) and `MCPServerHTTP` (SSE transport with `/sse`, `/messages`, `/tools/call`, `/health`)
- Tools: `list_models`, `run_prompt`, `chat_completion`, `ping`
- `modellens mcp serve --transport stdio|sse` CLI with provider resolution and signal handling

#### Benchmark Result Caching

- `packages/core/cache.py` — `ContentAddressableCache` with SHA-256 content-addressed keys, two-level directory prefix, full CRUD + status/listing
- `WorkloadRunner` now accepts optional `cache` parameter: checks cache before API calls, stores results after successful runs
- `BenchmarkSuite` accepts cache plumbing (parameter + forward reference)
- `modellens cache status|list|clear|inspect|config` CLI commands with rich table output
- Cache wired into `modellens workload run` by default (`--cache/--no-cache` toggle, `--cache-dir` option) with aggregate hit count display

#### OpenTelemetry Collector

- `packages/events/otel.py` — `OtelCollector` subscribes to all EventBus events and exports spans + metrics via OTLP (gRPC/HTTP, no hard dependency on SDK)
- RunLifecycleEvent → span lifecycle; CompletionEvent → LLM completion span + histogram; MetricEvent → gauges; TokenGenerated/Error/ToolCall events → counters
- Configurable via standard `OTEL_EXPORTER_OTLP_*` env vars
- `modellens otel status|serve|test` CLI commands with signal handling and SDK availability checks

#### Dashboard Authentication

- JWT token system (`packages/core/jwt_utils.py`) — stdlib-only, no PyJWT dependency
- Login page (`apps/dashboard/src/pages/login.astro`) with token input and session storage
- SSE authentication via `?token=` query parameter with JWT verification
- `modellens auth token --ttl <hours>` CLI for generating tokens

#### SQLite Migration

- `packages/core/results_store.py` — SQLite-backed `ResultsStore` with CRUD, filtering, pagination, and migration from `runs_index.json`
- `scripts/migrate_to_sqlite.py` and `modellens migrate sqlite --dry-run` CLI
- Integration tests (`tests/test_migrate_sqlite.py`) covering dry-run, full migration, empty index, missing index, and corrupt detail files

#### Standalone SSE Server

- `modellens sse serve --port N` — standalone EventBus SSE server that decouples streaming from benchmark processes
- `subscribe_existing=False` support for deferred subscription
- Dashboard auto-detection of standalone SSE servers

#### Unified Configuration

- Single `config.yaml` with `general:` + `devbench:` sections, validated by JSON Schema (`apps/cli/config_schema.json`)
- `apps/cli/config.json` deprecated with `_deprecated` and `_migration_guide` fields

#### Provider Plugin System

- Entry-point-based provider discovery via `pyproject.toml` entry-points
- `discover_providers()`, `get_provider()`, `get_provider_config()` with fallback to built-in registry for dev mode
- `LMStudioProvider` subclass with correct defaults (port 1234, key `lm-studio`)

#### Historical Regression Detection

- `packages/core/regression.py` — CUSUM/Page-Hinkley change-point detection engine with z-score fallback; `detect_regression()`, `detect_all()`, `RegressionAlert` dataclass
- `packages/core/regression.py` — `AlertStore` (SQLite persistence for alert history), `subscribe_to_run_events()` (auto-check after benchmark runs)
- `apps/cli/commands/regression.py` — `modellens regression detect|history|monitor|stats` with rich table output, JSON flag, and signal-safe monitoring
- `apps/dashboard/src/pages/api/regression/index.ts` — `GET /api/regression` dashboard endpoint with model/metric/severity filtering
- Unit tests (`tests/test_regression.py` — 61 tests covering CUSUM, z-score, dataclass, detection, AlertStore, edge cases)

#### Testing

- 11 pre-existing test failures resolved: patch target correction in `test_provider_clients.py`, abstract method contract fix in `test_mcp_bridge.py`
- Additional provider integration, MCP bridge, CLI command, workload, trace capture, and provider client tests
- Migration integration tests: dry-run, full migration, empty/missing index, corrupt detail files

### Changed

- Reorganized repo into strict monorepo: `apps/` (CLI + dashboard) and `packages/` (core system modules)
- Strengthened separation of concerns: `events` is fully decoupled (no dependency on core / providers); `providers` are fully stateless adapters
- `BenchmarkSuite` now emits `RunLifecycleEvent` (started / completed / failed) and `MetricEvent` for every benchmark result
- `OpenAICompatibleProvider.chat_completion()` emits `TokenGeneratedEvent` per streaming token and `CompletionEvent` on success / failure
- Provider URL handling replaced with `urllib.parse.urljoin()` / `urlparse()` across all providers and CLI commands
- `print()` calls replaced with structured logging (`packages.logging`) across providers, core, events, and CLI
- `except Exception:` eliminated — all exception handlers now use specific types
- Scoring robustness: fixed substring false-positives using regex word-boundaries; hardened evaluation logic across SWE / IF / agentic benchmarks
- Config system clarified: YAML (general benchmarks) and JSON (DevBench / Apple Silicon) — both explicitly preserved
- CI now fails on test failures (was previously `|| echo` — errors were invisible)
- Dashboard: major UI refresh, improved navigation, trace / replay workflows, workload reporting UX, leaderboard presentation
- Updated dashboard dependencies and frontend build configuration

### Fixed

- 11 pre-existing test failures: `test_provider_clients.py` (incorrect `patch` targets for `OpenAI` — subclasses import it from `openai_compatible.py`, not their own module; bare `Exception` side effects not caught by `requests.ConnectionError` handlers) and `test_mcp_bridge.py` (`FakeSkill` implemented `@property manifest` override instead of required `_create_manifest()` abstract method)
- Substring false-positive issues in scoring engine: `useState`, `useEffect`, `async`, `constructor`, `_variable_`
- Prompt mutation corruption: replaced `.replace()` with `re.sub()` with word boundaries
- Framework token corruption in prompt generator
- Provider compatibility edge cases: fallback `/api/tags` for older Ollama versions
- Cross-module import dependency violations: Ollama no longer depends on core
- Provider interoperability issues
- MCP bridge integration edge cases
- Provider health-check handling improvements
- Hardware detection reliability improvements
- Multiple benchmark execution edge cases

### Removed

- `LMStudioClient` — deprecated (thin wrapper retained for backward compatibility)
- Legacy benchmark-only assumptions in core execution paths
- Legacy benchmark scripts outside monorepo structure
- Redundant / outdated CLI helper scripts
- Legacy dashboard static-only build path (replaced with SSR mode)
- Additional obsolete benchmark artifacts and stale generated data

---

## 0.3.0 — 2026-06-04

### Added

#### Platform Foundation

- Modular CLI architecture
- Multi-provider ecosystem foundation
- Replay and observability infrastructure
- Expanded dashboard functionality
- Community leaderboard support
- Hardware profiling and system detection

#### Providers

- Ollama integration
- LM Studio integration improvements
- Provider abstraction layer

#### Dashboard

- Astro dashboard
- Leaderboard views
- Trace visualization
- Benchmark reporting

#### Benchmarking

- Prompt packs
- Benchmark execution engine
- Benchmark scoring framework
- Workload benchmarking foundation

### Vision

This release marks the beginning of Model Lens' transition from a benchmark harness toward a broader local AI observability platform focused on benchmarking, traces, replay, workloads, provider interoperability, and performance analysis.

---

## 0.1.0 — Initial Release

### Added

- 11 benchmark implementations (MMLU-Pro, GSM8K, HumanEval, etc.)
- DevBench v2 (Apple Silicon optimized workload system)
- Astro + React dashboard
- LM Studio provider integration
- GitHub Actions CI (initial)
- Prompt packs system
- Cloudflare Pages deployment

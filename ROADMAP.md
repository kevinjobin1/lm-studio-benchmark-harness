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
| **Phase 3** | LocalAI, KoboldCPP, Text Generation WebUI |

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

### V3 🚧
- Skill system (types, registry, lockfile) ✅
- Provider expansion (6 providers) ✅
- MCP bridge ✅
- WASM sandbox
- Workload evaluation ✅
- Regression detection


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
- [ ] Regression detection
- [ ] Skills runtime
- [ ] Skill registry
- [ ] WASM isolation
- [ ] MCP server mode

### V4 — OpenTelemetry for Local AI 🔮 Future

Potential initiatives:
- Trace schema standardization
- OpenTelemetry export
- VS Code extension
- IDE integrations
- Distributed agent traces
- Team collaboration

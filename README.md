# 🔬 Model Lens

> **Observability-first platform for local AI.** Trace, replay, compare, and understand how models behave on your hardware. Benchmarks are a feature — observability is the product.

[![CI](https://github.com/kevinjobin1/model-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/kevinjobin1/model-lens/actions/workflows/ci.yml)

---

> **Contributing**: Pre-commit hooks run ruff, ruff-format, and mypy on every commit. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup.

## Project Status

Model Lens is currently in active development.

Current focus areas:

- Local AI observability
- Trace capture and replay
- Workload evaluation
- Provider interoperability
- Model comparison tooling

Benchmarking remains supported, but observability is now the primary direction of the project.

## Screenshots

> *Screenshots coming soon. In the meantime, run the dashboard locally:*
> ```bash
> cd apps/dashboard && bun install && bun run dev
> ```

<!-- TODO: Add screenshot of dashboard overview page -->
<!-- TODO: Add screenshot of trace timeline replay -->
<!-- TODO: Add GIF of side-by-side model comparison -->

---

## Why Model Lens?

Most local AI tooling focuses on one layer:

- Benchmarking
- Chat interfaces
- Model serving
- Agent frameworks

Very few tools help developers understand what a model is actually doing on their machine.

Model Lens focuses on observability and gives you the full picture — execution traces, latency profiles, memory footprints, and real-world workload evaluations — so you can answer:

- **What** happened?
- **Which** model is better for my **workload**?
- **How** did **performance** change?
- **Why** did this model fail? **Why** did it happen?
- **Why** is this model _slower_ on my **hardware**?
- **Which** model performs best on my **actual** codebase?

---

## Current Features

### Observability (primary)

- **Event bus** — `TokenGenerated`, `CompletionEvent`, `MetricEvent`, `ErrorEvent`, `RunLifecycleEvent` emitted throughout the pipeline
- **Trace timeline viewer** — token-level execution replay with playback controls
- **SSE streaming** — real-time event bridge for the dashboard (`--sse-port N`)
- **Replay engine** — record and replay full execution sessions from disk
- **Run history** — browse, search, and compare past benchmark runs
- **Provider diagnostics** — health checks, model listing, connection status

### Evaluation

- **Workload evaluation** — test models on real projects (React, NestJS, Python, Rust)
- **Prompt packs** — versioned, shareable benchmark prompt collections
- **Statistical scoring** — multi-run variance, confidence intervals, failure analysis
- **Model comparison** — side-by-side trace diffing and metric comparison

### Benchmarking (secondary)

- MMLU-Pro, GSM8K, AIME, HumanEval, SWE-Bench Lite, IF-Eval
- Needle in a Haystack, BFCL, Speed/Latency, Memory, Creativity
- DevBench v2 — TypeScript/NestJS/React with execution-grounded scoring

### Infrastructure

- 6 providers: LM Studio, Ollama, Open WebUI, Jan, llama.cpp, vLLM
- All providers use OpenAI-compatible `/v1` endpoints
- CI enforcement: ruff lint, ruff format, mypy, pytest
- Pre-commit hooks

---

## Quick Start 

Using `uv` is recommended for dependency management and reproducibility.

```bash
# Install (using uv)
uv pip install -r requirements.txt

# Run workload evaluation (auto-detects models)
uv python apps/cli/modellens.py workload run --model qwen3.5-9b

# Run benchmarks (auto-detects models)
uv python apps/cli/modellens.py run --quick

# Compare two models
uv python apps/cli/modellens.py run --framework compare --models qwen3.5 gemma-4

# Use Ollama
uv python apps/cli/modellens.py run --provider ollama --models llama3.2
```

---

## Architecture

```
apps/
  cli/          ← Unified modellens CLI (Click)
  dashboard/    ← Astro + React observability dashboard
packages/
  events/       ← Event bus — decoupled observability events
  core/         ← Benchmark framework, trace capture, workload evaluation
  benchmarks/   ← 10+ benchmark implementations
  providers/    ← 6 provider adapters (LM Studio, Ollama, Open WebUI, Jan, llama.cpp, vLLM)
  skills/       ← Versioned, lockfile-verified skill system
  prompt_packs/ ← Community benchmark packs (React, NestJS, debugging, agentic)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

---

## Dashboard

The project includes an [Astro](https://astro.build) + React dashboard at `apps/dashboard/` for visualizing benchmark results, replaying execution traces, managing runs, and comparing models.

### Quick Start

```bash
cd apps/dashboard
bun install
bun run dev          # → http://localhost:4321
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check — uptime, started_at, version |
| `/api/status` | GET | Provider connection status, loaded models, hardware info |
| `/api/traces` | GET | List and query execution traces |
| `/api/traces/[id]` | GET | Individual trace data |
| `/api/run-benchmark` | POST | Start a benchmark process |
| `/api/run-benchmark/active` | GET | Currently running benchmark processes |

### Provider URL

By default the dashboard checks LM Studio at `http://127.0.0.1:1234/v1`. Override with:

```bash
LM_STUDIO_URL=http://192.168.1.50:1234/v1 bun run dev
```

---

## Documentation

- [ROADMAP.md](ROADMAP.md) — Product roadmap
- [VISION.md](VISION.md) — Why this project exists
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical design
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contributor guide
- [DESIGN.md](DESIGN.md) — Design system
- [CHANGELOG.md](CHANGELOG.md) — Release history
- [Run Schema](docs/specs/run-schema.md) — Canonical data model

---

## License

MIT

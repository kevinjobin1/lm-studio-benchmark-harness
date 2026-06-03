# 🔬 Model Lens

> Observability for local AI models. Not just benchmarks — full execution traces, replay, workload evaluation, and side-by-side comparison.

[![CI](https://github.com/kevinjobin1/model-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/kevinjobin1/model-lens/actions/workflows/ci.yml)

---

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

Most LLM tools give you a single benchmark score. Model Lens gives you the full picture — execution traces, latency profiles, memory footprints, and real-world workload evaluations — so you can answer:

- **Why** did this model fail?
- **Why** is this model slower on my hardware?
- **Which** model performs best on my **actual** codebase?

---

## Features

- 🔁 **Trace Replay** — Capture and replay model execution with token-level timing, play/pause, speed controls, and keyboard shortcuts
- 📊 **Observability** — TTFT, tokens/sec, memory pressure, run variance, failure breakdowns
- 🔬 **Workload Evaluation** — Evaluate models against real project codebases (NestJS, React, Rust, Python) with realistic coding tasks
- 🤝 **Side-by-Side Comparison** — 2-way and 3-way model comparison with per-step timing deltas
- 📦 **Prompt Packs** — Versioned, community-extensible benchmark collections (React, NestJS, debugging, agentic)
- 🖥️ **Dashboard** — Astro + React, Cloudflare Pages deployable, live API endpoints
- 🎯 **Skill System** — Versioned, sandboxed, lockfile-verified skill runtime for deterministic evaluation
- 🤖 **Multi-Provider** — LM Studio, Ollama, Open WebUI, Jan, llama.cpp, vLLM

---

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Run workload evaluation (auto-detects models)
python apps/cli/modellens.py workload run --model qwen3.5-9b

# Run benchmarks (auto-detects models)
python apps/cli/modellens.py run --quick

# Compare two models
python apps/cli/modellens.py run --framework compare --models qwen3.5 gemma-4

# Use Ollama
python apps/cli/modellens.py run --provider ollama --models llama3.2
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

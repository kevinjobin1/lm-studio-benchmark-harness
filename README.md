# 🔬 ModelLens

> Observability for local AI models. Benchmark, compare, replay, and understand how models actually perform on your hardware.

[![CI](https://github.com/kevinjobin1/lm-studio-benchmark-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/kevinjobin1/lm-studio-benchmark-harness/actions/workflows/ci.yml)

---

## Why ModelLens?

Most LLM benchmarks give you a single score. ModelLens gives you the full picture — execution traces, latency metrics, memory profiles, and side-by-side comparisons — so you can answer:

- Why did this model fail?
- Why is this model slower on my hardware?
- Which model performs best on my actual workload?

---

## Features

- 🔬 **Benchmarking** — MMLU-Pro, GSM8K, HumanEval, speed/latency, DevBench, and more
- 📊 **Observability** — TTFT, tokens/sec, memory, run variance
- 🔁 **Replay** — Capture and replay model execution traces
- 📦 **Prompt Packs** — Versioned, community-extensible benchmark collections
- 🖥️ **Dashboard** — Astro + React, Cloudflare Pages deployable
- 🤖 **Multi-provider** — LM Studio + Ollama support

---

## Quick Start

```bash
# Install
pip install -r requirements.txt

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
  cli/          ← Unified modellens CLI
  dashboard/    ← Astro + React dashboard
packages/
  core/         ← Benchmark framework
  benchmarks/   ← 10+ benchmark implementations
  providers/    ← LM Studio, Ollama adapters
  skills/       ← Extensible skill system
  prompt_packs/ ← Community benchmark packs
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

---

## Dashboard

The project includes an [Astro](https://astro.build) + React dashboard at `apps/dashboard/` for visualizing benchmark results, managing runs, and monitoring LM Studio connections.

### Quick Start

```bash
cd apps/dashboard
bun install
bun run dev          # → http://localhost:4321
```

### API Endpoints

The dashboard runs in server mode (`output: "server"`) with live API endpoints for the benchmark runner UI:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | LM Studio connection status, loaded models, hardware info |
| `/api/run-benchmark` | POST | Start a benchmark process (`{ quick: boolean }`) |
| `/api/run-benchmark/active` | GET | Currently running benchmark processes |
| `/api/run-benchmark/logs?pid=X` | GET | Live stdout/stderr for a process |
| `/api/run-benchmark/kill?pid=X` | POST | Kill a running process |

### LM Studio URL

By default the dashboard checks LM Studio at `http://127.0.0.1:1234/v1`. Override with:

```bash
LM_STUDIO_URL=http://192.168.1.50:1234/v1 bun run dev
```

See [apps/dashboard/README.md](apps/dashboard/README.md) for full documentation.

---

## Documentation

- [ROADMAP.md](ROADMAP.md) — Product roadmap
- [VISION.md](VISION.md) — Why this project exists
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical design
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contributor guide
- [DESIGN.md](DESIGN.md) — Design system
- [CHANGELOG.md](CHANGELOG.md) — Release history

---

## License

MIT

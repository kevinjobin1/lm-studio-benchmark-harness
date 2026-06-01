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
- 🖥️ **Dashboard** — Astro + React, GitHub Pages deployable
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

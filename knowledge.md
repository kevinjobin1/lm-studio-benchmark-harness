# Project knowledge

This file gives Codebuff context about your project: goals, commands, conventions, and gotchas.

## Overview
Model Lens — an open-source observability and evaluation platform for local AI models. Supports LM Studio and Ollama providers. Monorepo with `apps/` (CLI + dashboard) and `packages/` (core, benchmarks, providers, skills, prompt_packs).

Primary entry point: **`apps/cli/modellens.py`** — unified Click CLI with `run`, `info`, `leaderboard` commands.

## Quickstart
- **Setup:** `pip install -r requirements.txt`
- **Run:** `python apps/cli/modellens.py run --quick`
- **Ollama:** `python apps/cli/modellens.py run --provider ollama --models llama3.2`
- **Dashboard:** `cd apps/dashboard && npm install && npm run dev`
- **Test:** No formal test suite exists. Benchmarks are self-validating.

## Architecture
```
apps/
  cli/                     ← Unified modellens CLI (Click)
    modellens.py           ←   Entry point: run, info, leaderboard
    benchmark.py           ←   General harness (delegated from modellens)
    bench_apple_silicon_v2.py ← DevBench v2 (delegated from modellens)
    scoring.py             ←   Comprehensive evaluation
    evaluators.py          ←   Pluggable evaluators
    prompt_generator.py    ←   Parameterized prompt generation
    config_manager.py      ←   Config loading/validation
    config.yaml / config.json ← Benchmark configs
    run_manifest.py        ←   Reproducibility manifests
    reporting.py           ←   Report generation
    apple_silicon_monitor.py ← Hardware monitoring
  dashboard/               ← Astro + React dashboard (see DESIGN.md)
    src/
      components/          ←   React components
      layouts/             ←   Astro layouts
      pages/               ←   Route pages + API routes
      lib/                 ←   Shared utilities
packages/
  __init__.py
  core/                    ← Benchmark framework
    __init__.py            ←   Exports: BenchmarkSuite, LMStudioClient, etc.
    benchmark.py           ←   Core classes
    evaluators/            ←   Agentic evaluators
  benchmarks/              ← 11 benchmark implementations
  providers/               ← Provider adapters + framework integrations
    base.py                ←   ProviderAdapter ABC + shared dataclasses
    ollama.py              ←   OllamaClient
    lm_eval_integration.py ←   LM Eval bridge
    openbench_integration.py ← OpenBench bridge
    mcp/                   ←   MCP bridge (future)
  skills/                  ← Extensible skill system
  prompt_packs/            ← Versioned benchmark prompt collections
```

## Conventions
- **Design system:** Dashboard UI follows the Kinetic Logic design system — see `DESIGN.md` for colors, typography, spacing, elevation, and component patterns.
- **Formatting:** No linter/formatter configured. Python uses standard 4-space indentation.
- **CLI:** Unified `modellens` CLI uses Click. Delegates to `benchmark.py` (general) or `bench_apple_silicon_v2.py` (devbench).
- **Config:** `apps/cli/config.yaml` (general) and `apps/cli/config.json` (devbench).
- **API:** All code talks to providers via OpenAI-compatible `/v1` endpoints. LM Studio: `localhost:1234`, Ollama: `localhost:11434`.
- **Output:** `results/` directory.
- **Imports:** Uses `from core import ...` and `from benchmarks import ...` pattern (with `packages/` on sys.path).
- **Type hints:** Used consistently with `dataclasses` for result objects.

## Gotchas
- **No formal tests** — there is no test suite, no pytest, no CI. Validation is manual.
- **Two parallel systems** — `benchmark.py` (general, `config.yaml`) and `bench_apple_silicon_v2.py` (Apple Silicon, `config.json`) share some modules (`scoring.py`, `evaluators.py`) but are separate entry points with different config formats. Don't mix them up.
- **`scipy` is optional** — `scoring.py` falls back to normal approximation for confidence intervals if scipy isn't installed.
- **`ts-node`/`tsc`/`eslint` are optional** — TypeScript execution scoring degrades gracefully if these aren't installed.
- **Config files are not interchangeable** — `config.yaml` uses nested YAML; `config.json` uses a flat JSON structure with different schemas.
- **Hardware target** — optimized for MacBook Pro M3, 18GB unified memory, 7B-9B models. Memory/thermal monitoring is macOS-specific.

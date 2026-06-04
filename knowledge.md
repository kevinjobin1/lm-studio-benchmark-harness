# Project knowledge

This file documents the **operational truth** of Model Lens:
how the system behaves today, how to run it, and key implementation constraints.

It is intentionally different from:
- `README.md` → user-facing overview
- `ARCHITECTURE.md` → system design
- `VISION.md` → philosophy
- `ROADMAP.md` → future evolution
- `AGENTS.md` → canonical execution truth

---

## Overview

Model Lens is a **local AI observability platform** with built-in benchmarking, trace capture, replay, and workload evaluation. It supports 6 local providers: LM Studio, Ollama, llama.cpp, vLLM, Open WebUI, and Jan.

**Mental model**: A distributed event-sourced execution tracer for local LLM runs. Benchmarks are a feature — observability is the product. The core asset is the trace stream.

Primary entry point: **`apps/cli/modellens.py`** — unified Click CLI with `run`, `info`, `leaderboard`, `models`, `workload`, `compare`, `health`.

## Quickstart
- **Setup:** `pip install -r requirements.txt`
- **Dev deps:** `pip install ".[dev]" && pre-commit install`
- **Run:** `python apps/cli/modellens.py run --quick`
- **Ollama:** `python apps/cli/modellens.py run --provider ollama --models llama3.2`
- **Dashboard:** `cd apps/dashboard && npm install && npm run dev`
- **Test:** `pytest tests/ -v`

## Architecture
```
apps/
  cli/                     ← Unified modellens CLI (Click)
    commands/              ←   run, info, models, health, leaderboard, workload, publish
    modellens.py           ←   Entry point
    benchmark.py           ←   General harness (delegated from modellens)
    bench_apple_silicon_v2.py ← DevBench v2 (delegated from modellens)
    scoring.py             ←   Comprehensive evaluation
    evaluators.py          ←   Pluggable evaluators
    prompt_generator.py    ←   Parameterized prompt generation
  dashboard/               ← Astro + React dashboard (see DESIGN.md)
packages/
  logging.py              ← Structured logging (Rich console + file output)
  events/                 ← Event bus — typed, thread-safe observability events
    sse.py                ←   SSE bridge for dashboard streaming
    replay.py             ←   Event replay writer (persists events to disk)
  core/                   ← Benchmark framework + trace capture + workload
    benchmark.py           ←   Core classes (LMStudioClient deprecated)
    trace_capture.py       ←   Token-level execution tracing
    trace_schema.py        ←   Trace dataclasses
    hardware.py            ←   Hardware detection
    workload/              ←   Workload evaluation engine
  benchmarks/              ← 11 benchmark implementations
  providers/               ← 6 provider adapters (all OpenAI-compatible /v1)
    base.py                ←   ProviderAdapter ABC + URL utilities
    openai_compatible.py   ←   OpenAICompatibleProvider with event bus integration
    ollama.py              ←   OllamaClient
  skills/                  ← Extensible skill system
  prompt_packs/            ← Versioned benchmark prompt collections
```

## Conventions
- **Design system:** Dashboard UI follows the Kinetic Logic design system — see `DESIGN.md`.
- **Formatting:** `ruff format` (double quotes, 100 char lines). CI enforces via `.github/workflows/ci.yml`.
- **Linting:** `ruff check` with pycodestyle, Pyflakes, isort, bugbear, pep8-naming. Pre-commit enforces.
- **Type checking:** `MYPYPATH=packages mypy packages/ apps/cli/`. Pre-commit + CI enforce.
- **CI:** Ruff lint, ruff format check, mypy, pytest — all strict, all on every push.
- **CLI:** Unified `modellens` CLI uses Click. Delegates to `benchmark.py` (general) or `bench_apple_silicon_v2.py` (devbench).
- **Config:** `apps/cli/config.yaml` (general) and `apps/cli/config.json` (devbench). Not interchangeable.
- **API:** All code talks to providers via OpenAI-compatible `/v1` endpoints.
- **URL handling:** Use `urllib.parse.urljoin()` and the helpers in `providers.base` (`normalize_base_url`, `get_root_url`, `url_join`). No `.rstrip()`, `.removesuffix()`, or string concatenation for URLs.
- **Logging:** `from packages.logging import get_logger`. No raw `print()` for observability data.
- **Events:** Emit events via the `EventBus` (typed, thread-safe). Provider tokens → `TokenGeneratedEvent`, results → `MetricEvent`, lifecycle → `RunLifecycleEvent`.
- **Imports:** Uses `from core import ...` and `from benchmarks import ...` pattern (with `packages/` on sys.path).
- **Type hints:** Used consistently with `dataclasses` for result objects.

## Gotchas
- **Dual-authority benchmark systems** — `benchmark.py` (general, `config.yaml`) and `bench_apple_silicon_v2.py` (Apple Silicon, `config.json`) are **both first-class and intentionally preserved**. They share scoring + evaluation modules but differ in config format and execution pipeline. Do not try to merge them — they serve different purposes.
- **`scipy` is optional** — `scoring.py` falls back to normal approximation for confidence intervals if scipy isn't installed.
- **`ts-node`/`tsc`/`eslint` are optional** — TypeScript execution scoring degrades gracefully if these aren't installed.
- **Config files are not interchangeable** — `config.yaml` uses nested YAML; `config.json` uses a flat JSON structure with different schemas.
- **Hardware target** — optimized for MacBook Pro M3, 18GB unified memory, 7B-9B models. Memory/thermal monitoring is macOS-specific.

## Key modules

| Module | Responsibility |
|--------|---------------|
| `modellens.py` | CLI orchestration |
| `benchmark.py` | General evaluation engine |
| `bench_apple_silicon_v2.py` | Apple Silicon DevBench v2 |
| `scoring.py` | Model evaluation logic |
| `trace_capture.py` | Token-level observability |
| `events/` | Event bus, SSE streaming, replay |
| `providers/` | Model connectivity layer (6 providers) |
| `logging.py` | Structured logging |

## Data flow

```
User CLI command
    ↓
Provider selection + resolution
    ↓
Request sent to model (OpenAI-compatible /v1)
    ↓
Streaming tokens captured → TokenGeneratedEvent × N
    ↓
CompletionEvent emitted
    ↓
MetricEvents emitted (scores)
    ↓
RunLifecycleEvent emitted (started / completed / failed)
    ↓
Trace assembled → SSE stream (dashboard) + replay file (disk)
    ↓
Results stored → Dashboard visualization
```

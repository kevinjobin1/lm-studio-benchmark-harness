# Project knowledge

This file gives Codebuff context about your project: goals, commands, conventions, and gotchas.

## Overview
LM Studio Benchmark Harness — a Python benchmark suite for evaluating local AI models via LM Studio's OpenAI-compatible API on Apple Silicon. Two major entry points:
- **`benchmark.py`** — General-purpose harness (MMLU-Pro, GSM8K, HumanEval, SWE-bench, IFEval, Needle-in-Haystack, BFCL, speed/latency, memory, creativity). Supports custom, LM Eval, and OpenBench frameworks. Uses `config.yaml`.
- **`bench_apple_silicon_v2.py`** — DevBench v2: TypeScript/NestJS/React-focused benchmark with statistical rigor (5 runs/prompt), execution-grounded scoring (ts-node, tsc, eslint), developer realism metrics. Uses `config.json`.

## Quickstart
- **Setup:** `pip install -r requirements.txt`
- **Dev (general):** `python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model`
- **Dev (Apple Silicon):** `python bench_apple_silicon_v2.py` (auto-detects LM Studio models)
- **Dev (Apple Silicon v1):** `python bench_apple_silicon.py`
- **Generate X thread:** `python x_thread_generator.py`
- **Test:** No formal test suite exists. Benchmarks are self-validating.

## Architecture
```
benchmark.py              # General harness (click CLI, uses config.yaml)
bench_apple_silicon_v2.py # DevBench v2 (argparse CLI, uses config.json)
bench_apple_silicon.py    # DevBench v1 (simpler, no variance)
scoring.py                # Comprehensive evaluation: variance stats, execution-grounded scoring, failure taxonomy, tokenization-aware metrics
evaluators.py             # Pluggable evaluators: JSON schema, regex constraints, keyword match, numerical answer, code execution, composite
prompt_generator.py       # Parameterized prompt generation for DevBench (code/frontend/reasoning/math/instruction/debugging)
config_manager.py         # Config loading/validation
config.yaml               # General benchmark config
config.json               # DevBench v2 canonical config
config_schema.json        # JSON schema for config validation
run_manifest.py           # Reproducibility manifests (git SHA, checksums)
reporting.py              # Report generation (HTML/JSON/CSV)
apple_silicon_monitor.py  # Hardware monitoring (RAM, thermal, swap)
x_thread_generator.py     # Auto-generate X/Twitter threads from results
leaderboard.html          # Static leaderboard page

benchmark/
  core.py                 # BenchmarkSuite, LMStudioClient base classes
  __init__.py
benchmarks/
  __init__.py
  mmlu_pro.py, gsm8k.py, aime.py, humaneval.py, swe_bench.py,
  if_eval.py, needle_haystack.py, bfcl.py, speed_latency.py,
  memory.py, creativity.py, math_benchmarks.py, coding.py
integrations/
  __init__.py
  lm_eval_integration.py  # LM Eval framework integration
  openbench_integration.py# OpenBench integration
```

## Conventions
- **Design system:** Dashboard UI follows the Kinetic Logic design system — see `docs/DESIGN.md` for colors, typography, spacing, elevation, and component patterns.
- **Formatting:** No linter/formatter configured. Python uses standard 4-space indentation.
- **CLI:** General harness uses `click`; DevBench v2 uses `argparse`.
- **Config:** General harness reads `config.yaml`; DevBench v2 reads `config.json`.
- **API:** All code talks to LM Studio's OpenAI-compatible endpoint (`http://localhost:1234/v1`, default key: `lm-studio`).
- **Output:** General harness → `results/timestamp/`; DevBench v2 → `devbench_results/`.
- **Imports:** Uses `from benchmark.core import ...` and `from benchmarks import ...` pattern.
- **Type hints:** Used consistently with `dataclasses` for result objects.

## Gotchas
- **No formal tests** — there is no test suite, no pytest, no CI. Validation is manual.
- **Two parallel systems** — `benchmark.py` (general, `config.yaml`) and `bench_apple_silicon_v2.py` (Apple Silicon, `config.json`) share some modules (`scoring.py`, `evaluators.py`) but are separate entry points with different config formats. Don't mix them up.
- **`scipy` is optional** — `scoring.py` falls back to normal approximation for confidence intervals if scipy isn't installed.
- **`ts-node`/`tsc`/`eslint` are optional** — TypeScript execution scoring degrades gracefully if these aren't installed.
- **Config files are not interchangeable** — `config.yaml` uses nested YAML; `config.json` uses a flat JSON structure with different schemas.
- **Hardware target** — optimized for MacBook Pro M3, 18GB unified memory, 7B-9B models. Memory/thermal monitoring is macOS-specific.

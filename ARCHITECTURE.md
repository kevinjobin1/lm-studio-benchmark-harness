# ModelLens Architecture

## Monorepo structure

```
apps/
  cli/                  ← Unified `modellens` CLI (Click-based)
  dashboard/            ← Astro + React dashboard (see DESIGN.md)
  docs/                 ← Documentation site
packages/
  __init__.py
  core/                 ← Benchmark framework
    __init__.py         ←   Exports: BenchmarkSuite, LMStudioClient, Benchmark, etc.
    benchmark.py        ←   Core classes: BenchmarkSuite, LMStudioClient, MemoryMonitor
    evaluators/         ←   Pluggable evaluation strategies
      agentic.py        ←     Agentic response evaluation (hallucination detection)
  benchmarks/           ← Benchmark implementations
    mmlu_pro.py         ←   MMLU-Pro multiple choice
    gsm8k.py            ←   Grade school math
    coding.py           ←   HumanEval-style code generation
    swe_bench.py        ←   Software engineering tasks
    if_eval.py          ←   Instruction following
    needle_haystack.py  ←   Long context retrieval
    bfcl.py             ←   Function calling
    speed_latency.py    ←   Tokens/sec, TTFT, throughput
    memory.py           ←   RAM / VRAM profiling
    creativity.py       ←   Open-ended generation quality
    math_benchmarks.py  ←   AIME and other math benchmarks
  providers/            ← Provider adapters + framework integrations
    __init__.py         ←   Exports: ProviderAdapter, OllamaClient, integration runners
    base.py             ←   Abstract ProviderAdapter + shared dataclasses
    ollama.py           ←   OllamaClient (OpenAI-compatible /v1 API)
    lm_eval_integration.py  ← LM Eval framework bridge
    openbench_integration.py ← OpenBench bridge
    mcp/                ←   MCP bridge (future)
  skills/               ← Extensible skill system
    __init__.py
    types.py            ←   Skill types and interfaces
    registry.py         ←   Skill registry
    lockfile.py         ←   modellens.lock management
    agentic_prompts.py  ←   Agentic coding prompt generation
    builtins/           ←   Built-in skills (json_parse, diff, read_file, write_file)
  prompt_packs/         ← Versioned benchmark collections
    react-pack/         ←   React coding prompts
    nestjs-pack/        ←   NestJS backend prompts
    debugging-pack/     ←   Real-world debugging scenarios
    nestjs-agentic-pack/←   Agentic NestJS prompts (Kafka, Prisma, cache, pipes)
```

---

## Package responsibilities

| Package | Responsibility | Depends on |
|---------|---------------|------------|
| `core` | Benchmark framework (suite, client, monitor) | `providers` (for APICallMetrics) |
| `benchmarks` | Individual benchmark implementations | `core` |
| `providers` | Provider adapters + framework integrations | (self-contained) |
| `skills` | Extensible skill system | (self-contained) |
| `prompt_packs` | Benchmark prompt collections | (static data) |

---

## Data flow

```
User / Dashboard
    │
    ▼
modellens.py (CLI entry point)
    │
    ├──[devbench]──→ bench_apple_silicon_v2.py
    │                   └──→ LMStudioClient / OllamaClient
    │
    ├──[general]───→ core.BenchmarkSuite
    │                   ├──→ benchmarks/* (11 implementations)
    │                   └──→ LMStudioClient / OllamaClient
    │
    └──[compare]──→ both frameworks
    │
    ▼
Results (JSON, HTML, CSV)  →  Dashboard (Astro + React)  →  Cloudflare Pages
```

---

## Provider architecture

```
ProviderAdapter (ABC)
    │
    ├── LMStudioClient  (packages/core/benchmark.py)
    │     └── OpenAI-compatible /v1/chat/completions
    │
    └── OllamaClient    (packages/providers/ollama.py)
          └── OpenAI-compatible /v1/chat/completions
              (fallback: /api/tags for model listing)

Shared types (packages/providers/base.py):
    Model, RunRequest, RunResult, APICallMetrics, ProviderMetrics
```

---

## Key boundaries

1. **Core never imports from benchmarks.** Individual benchmarks import from core, not vice versa.
2. **Providers are self-contained.** OllamaClient depends only on base.py, not on core.
3. **CLI is the only entry point.** The dashboard delegates to modellens.py via subprocess spawn.
4. **Skills are lazy-loaded.** Registered at startup, executed on demand.
5. **Prompt packs are static data.** No code execution, just JSON/YAML prompt definitions.

---

## App navigation

```
ModelLens
├── Overview         ← System status, active benchmarks, recent runs
├── Models           ← Per-model detail pages with metrics and traces
├── Compare          ← Side-by-side model comparison
├── Replay           ← Trace playback with timeline controls
├── Prompt Packs     ← Browse and manage prompt packs
├── Skills           ← Skill registry and management
├── Runs             ← Historical benchmark runs
├── Settings         ← Provider configuration, hardware info
```

---

## Data model

### Model
- `id` — Unique model identifier
- `name` — Display name
- `provider` — LM Studio, Ollama, etc.
- `parameters` — Parameter count or tag (e.g., "7b", "latest")
- `quantization` — Quantization level

### Run
- `id` — Unique run identifier
- `model` — Model used
- `promptPack` — Prompt pack reference
- `timestamp` — Execution timestamp

### Trace
- `id` — Unique trace identifier
- `runId` — Parent run reference
- `events` — Ordered list of trace events (prompt sent, first token, reasoning, response complete)

### Metric
- `ttft` — Time to first token (ms)
- `tokensPerSecond` — Generation throughput
- `memory` — RAM usage (MB)
- `latency` — Total execution time (ms)

### Artifact
- `response` — Full model response text
- `logs` — Execution logs
- `screenshots` — Dashboard captures (future)

---

## Design system

All dashboard UI follows the **Kinetic Logic** design system. See [DESIGN.md](DESIGN.md) for colors, typography, spacing, elevation, and component patterns.

---

## Technology stack

| Layer | Technology |
|-------|-----------|
| CLI | Python 3.10+, Click, Rich |
| Core framework | Python 3.10+, OpenAI SDK, psutil |
| Dashboard | Astro 5, React 18, TypeScript |
| Providers | Python requests, OpenAI SDK |
| Deployment | Cloudflare Pages |

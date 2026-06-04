# Model Lens Architecture

## Monorepo structure

```
apps/
  cli/                  ← Unified `modellens` CLI (Click-based)
  dashboard/            ← Astro + React dashboard (see DESIGN.md)
  docs/                 ← Documentation site
packages/
  logging.py           ← Structured logging (Rich console + file output)
  events/               ← Event bus — decoupled observability events
    __init__.py         ←   EventBus, event types (TokenGenerated, Completion, Metric, Tool, Error, RunLifecycle)
    sse.py              ←   EventBusSSEServer — live dashboard streaming
    replay.py           ←   EventBusReplayWriter — persists events to disk
  core/                 ← Benchmark framework + trace capture + workload evaluation
    __init__.py         ←   Exports: BenchmarkSuite, TraceCapture, etc.
    benchmark.py        ←   Core classes: BenchmarkSuite, Benchmark, MemoryMonitor (LMStudioClient deprecated)
    trace_capture.py    ←   TraceCapture (token-level timing context manager)
    trace_schema.py     ←   Trace, TraceEvent, TraceMetrics dataclasses
    hardware.py         ←   Hardware detection (CPU, GPU, RAM, OS)
    workload/           ←   Workload evaluation engine (ProjectLoader, TaskGenerator, WorkloadRunner, WorkloadScorer)
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
    workload_bench.py   ←   Workload evaluation benchmark wrapper
  providers/            ← Provider adapters (6 providers — all OpenAI-compatible /v1)
    __init__.py         ←   Exports: all provider clients + integration runners
    base.py             ←   Abstract ProviderAdapter + shared dataclasses + URL utilities
    openai_compatible.py←   OpenAICompatibleProvider — base class with event bus integration
    ollama.py           ←   OllamaClient
    openwebui.py        ←   Open WebUI client
    jan.py              ←   Jan client
    llamacpp.py         ←   llama.cpp client
    vllm.py             ←   vLLM client
    lm_eval_integration.py  ← LM Eval framework bridge
    mcp/                ←   MCP bridge (future)
  skills/               ← Extensible skill system
    __init__.py
    types.py            ←   Skill types and interfaces
    registry.py         ←   Skill registry (validated against modellens.lock)
    lockfile.py         ←   modellens.lock management
    agentic_prompts.py  ←   Agentic coding prompt generation
    builtins/           ←   Built-in skills (json_parse, diff, read_file, write_file)
  prompt_packs/         ← Versioned benchmark collections
    react-pack/         ←   React coding prompts
    nestjs-pack/        ←   NestJS backend prompts
    debugging-pack/     ←   Real-world debugging scenarios
    nestjs-agentic-pack/←   Agentic NestJS prompts (Kafka, Prisma, cache, pipes)
docs/
  specs/
    run-schema.md       ←   Formal Run schema specification
```

---

## Package responsibilities

| Package | Responsibility | Depends on |
|---------|---------------|------------|
| `events` | Event bus — publish/subscribe for all observability events | (self-contained) |
| `core` | Benchmark framework, trace capture, workload evaluation | `providers` (for APICallMetrics) |
| `benchmarks` | Individual benchmark implementations | `core` |
| `providers` | Provider adapters + framework integrations | (self-contained) |
| `skills` | Extensible skill system | (self-contained) |
| `prompt_packs` | Benchmark prompt collections | (static data) |

---

## Event-driven architecture

The event bus (`packages/events/`) is the central nervous system of Model Lens. It decouples data producers from data consumers using typed events:

```
                            Event Bus
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   Provider calls          Benchmark runs          Tool execution
        │                       │                       │
        ▼                       ▼                       ▼
   TokenGenerated          MetricEvent             ToolCallEvent
   CompletionEvent         RunLifecycleEvent       ErrorEvent
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                  ┌─────────────┼─────────────┐
                  │             │             │
              Metrics        Traces        Dashboard
              Engine         Engine         (SSE/WS)
```

### Event types

| Event | Source | Consumers |
|-------|--------|-----------|
| `TokenGeneratedEvent` | `OpenAICompatibleProvider` streaming | TraceCapture, Dashboard (SSE) |
| `CompletionEvent` | `OpenAICompatibleProvider` response | MetricsEngine, ResultsCollector |
| `MetricEvent` | `BenchmarkSuite` / any component | Dashboard, ReplayEngine |
| `ToolCallEvent` | Skill runtime | AgenticEvaluator, TraceCapture |
| `ErrorEvent` | Any component | Dashboard, Alerts |
| `RunLifecycleEvent` | CLI entry point / `BenchmarkSuite` | ResultsCollector, Dashboard |

### Why events?

1. **Decoupling** — Benchmarks don't need to know about the dashboard. They emit events; the dashboard consumes them.
2. **Extensibility** — New consumers (MCP server, replay engine, alert system) just subscribe.
3. **Observability** — Every event is timestamped and traceable back to its source.
4. **Testing** — Events can be recorded and replayed for deterministic test scenarios.

---

## Data flow

```
User / Dashboard
    │
    ▼
modellens.py (CLI entry point)
    │
    ├──[workload]──→ core.workload.*
    │                   ├──→ ProjectLoader (load real projects)
    │                   ├──→ TaskGenerator (generate coding tasks)
    │                   ├──→ WorkloadRunner (run model on tasks)
    │                   └──→ WorkloadScorer (5-axis scoring)
    │
    ├──[devbench]──→ bench_apple_silicon_v2.py
    │                   └──→ ProviderAdapter (LM Studio / Ollama / etc.)
    │
    ├──[general]───→ core.BenchmarkSuite
    │                   ├──→ benchmarks/* (11 implementations)
    │                   └──→ ProviderAdapter
    │
    └──[compare]──→ both frameworks
    │
    ▼
Results + Traces → Event Bus → Dashboard (Astro + React) → Cloudflare Pages
```

---

## Provider architecture

LM Studio is treated as an OpenAI-compatible endpoint rather than a dedicated provider implementation.

```
ProviderAdapter (ABC — packages/providers/base.py)
    ├── OllamaClient
    ├── OpenWebUIClient
    ├── JanClient
    ├── LlamaCppClient
    ├── VLLMClient
    └── OpenAICompatibleClient

All use OpenAI-compatible /v1/chat/completions endpoints.

Shared types (packages/providers/base.py):
    Model, RunRequest, RunResult, APICallMetrics, ProviderMetrics
```

### Provider ports and defaults

| Provider | Default URL | Auto-detect probe |
|----------|-------------|-------------------|
| LM Studio | `http://localhost:1234/v1` | `/v1/models` |
| Ollama | `http://localhost:11434/v1` | `/api/tags` |
| llama.cpp | `http://localhost:8080/v1` | `/v1/models` |
| vLLM | `http://localhost:8000/v1` | `/v1/models` |
| Open WebUI | `http://localhost:3000/api/v1` | `/api/v1/models` |
| Jan | `http://localhost:1337/v1` | `/v1/models` |

Auto-detection probes in order: LM Studio → Ollama → llama.cpp → vLLM → Open WebUI → Jan.

---

## Benchmark architecture (dual-authority)

Model Lens intentionally maintains **two independent benchmark systems**:

| System | File | Config | Purpose |
|--------|------|--------|---------|
| General suite | `apps/cli/benchmark.py` | `config.yaml` (YAML) | MMLU-Pro, GSM8K, HumanEval, SWE-Bench Lite, IF-Eval, etc. |
| DevBench v2 | `apps/cli/bench_apple_silicon_v2.py` | `config.json` (JSON, deprecated) | TypeScript/NestJS/React evaluation, Apple Silicon optimized |

Both systems are **first-class and equally authoritative** — one is not replacing the other, and they are not migration phases toward a unified pipeline. They share scoring/evaluation modules (`apps/cli/scoring.py`, `apps/cli/evaluators.py`, `apps/cli/prompt_generator.py`) but differ in:

- **Config format**: YAML (nested) vs JSON (flat, deprecated)
- **Execution pipeline**: `BenchmarkSuite` delegation vs direct `AppleSiliconBenchmarkV2`
- **Scoring strategy**: Statistical multi-benchmark scores vs execution-grounded developer scores
- **Hardware targeting**: Cross-platform vs Apple Silicon-specific (MPS, ANE, unified memory)

**DO NOT merge these systems.** They serve different evaluation use cases and are intentionally preserved.

---

## Key boundaries

1. **Events package is self-contained.** No dependencies on core, providers, or benchmarks.
2. **Core never imports from benchmarks.** Individual benchmarks import from core, not vice versa.
3. **Providers are self-contained.** Each client depends only on base.py, not on core.
4. **CLI is the only entry point.** The dashboard delegates to modellens.py via subprocess spawn.
5. **Skills are lazy-loaded.** Registered at startup, validated against `modellens.lock`, executed on demand.
6. **Prompt packs are static data.** No code execution, just JSON/YAML prompt definitions.

---

## App navigation

```
Model Lens
├── Overview         ← System status, active benchmarks, recent runs
├── Models           ← Per-model detail pages with metrics and traces
├── Compare          ← Side-by-side model comparison (2-way / 3-way)
├── Replay           ← Trace playback with timeline controls
├── Workload         ← Workload evaluation info and results
├── Prompt Packs     ← Browse and manage prompt packs
├── Skills           ← Skill registry and management
├── Runs             ← Historical benchmark runs
├── Settings         ← Provider configuration, hardware info
```

---

## Data model

The canonical data model is documented in [docs/specs/run-schema.md](docs/specs/run-schema.md).

### Core entities

```
Run
 ├── id             — Unique run identifier
 ├── model          — Model + provider + metadata
 ├── workload       — What was evaluated (benchmark, prompt pack, project)
 ├── trace          — Execution timeline (events, metrics, artifacts)
 ├── metrics        — Scores, performance, statistics
 ├── artifacts      — Raw response, logs, errors
 └── config         — Evaluation parameters snapshot
```

### Supporting types

- **Trace** — Token-level execution timeline (events, metrics, artifacts)
- **Metric** — Numeric measurements (TTFT, tokens/sec, memory, scores)
- **Event** — Typed observability events (token generated, tool called, error)
- **Artifact** — Raw outputs (response text, logs, screenshots)

---

## Design system

All dashboard UI follows the **Kinetic Logic** design system. See [DESIGN.md](DESIGN.md) for colors, typography, spacing, elevation, and component patterns.

---

## Technology stack

| Layer | Technology |
|-------|-----------|
| CLI | Python 3.10+, Click, Rich |
| Core framework | Python 3.10+, OpenAI SDK, psutil |
| Event bus | Python dataclasses + asyncio |
| Dashboard | Astro 5, React 18, TypeScript |
| Providers | Python requests, OpenAI SDK |
| Skills | Python ABC, JSON schemas, lockfile verification |
| Deployment | Cloudflare Pages |


### Replay Pipeline

```mermaid
TraceCapture
    ↓
Trace Events
    ↓
SSE Stream
    ↓
Dashboard Timeline
    ↓
Replay Viewer
```

## Workload Evaluation Architecture

```mermaid
Project
   ↓
Task Generation
   ↓
Execution
   ↓
Trace Capture
   ↓
Scoring
   ↓
Replayable Results
```

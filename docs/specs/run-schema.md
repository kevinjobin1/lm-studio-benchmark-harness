# Run Schema

> The canonical data model for a single model evaluation run.
>
> Every benchmark run, trace capture, workload evaluation, and comparison is a **Run**.
> This is the central entity in Model Lens — everything else is derived from it.

---

## Object Model

```
Run
 ├── id            
 ├── model         
 ├── provider      
 ├── workload       ← What was evaluated (benchmark name, prompt pack, project)
 ├── trace          ← Execution timeline (token-level events)
 ├── metrics        ← Numeric measurements (latency, throughput, scores)
 ├── artifacts      ← Raw outputs (response text, logs, errors)
 └── config         ← Snapshot of evaluation parameters
```

---

## JSON Schema

```json
{
  "run": {
    "id": "run_20240601_123456_qwen-3.5-9b",
    "version": "1.0.0",
    
    "model": {
      "id": "qwen-3.5-9b-coder",
      "provider": "lm-studio",
      "parameters": "9b",
      "quantization": "Q4_K_M",
      "size_bytes": 5830000000
    },
    
    "provider": {
      "name": "lm-studio",
      "endpoint": "http://localhost:1234/v1",
      "version": "0.3.10"
    },
    
    "workload": {
      "type": "benchmark",           // benchmark | prompt_pack | workload_project
      "name": "mmlu_pro",
      "category": "reasoning",
      "version": "1.0.0"
    },
    
    "trace": {
      "trace_id": "trace_abc123def456",
      "started_at": "2024-06-01T12:34:56.000Z",
      "completed_at": "2024-06-01T12:35:02.000Z",
      "events": [
        {
          "id": "e0",
          "type": "system",
          "label": "System Instruction",
          "timing_ms": 0,
          "status": "success"
        },
        {
          "id": "e1",
          "type": "prompt",
          "label": "Prompt Sent",
          "detail": "What is the capital of France?",
          "timing_ms": 0,
          "status": "success"
        },
        {
          "id": "e2",
          "type": "token",
          "label": "Token 1",
          "detail": "Paris",
          "timing_ms": 150,
          "status": "success"
        },
        {
          "id": "e3",
          "type": "response",
          "label": "Response Complete",
          "detail": "Paris is the capital of France.",
          "timing_ms": 320,
          "status": "success"
        }
      ],
      "metrics": {
        "ttft_ms": 150,
        "tokens_per_second": 45.2,
        "total_tokens": 15,
        "prompt_tokens": 8,
        "completion_tokens": 7,
        "total_latency_ms": 320,
        "memory_pressure_mb": 1240,
        "token_timings_ms": [150, 25, 18, 22, 20, 19, 21]
      },
      "artifacts": {
        "response": "Paris is the capital of France.",
        "logs": ["2024-06-01T12:34:56.001Z Starting generation..."],
        "errors": []
      }
    },
    
    "metrics": {
      "scores": {
        "correctness": 0.95,
        "completeness": 1.0,
        "code_quality": 0.85,
        "style_match": 0.90,
        "efficiency": 0.75
      },
      "performance": {
        "tokens_per_sec": 45.2,
        "normalized_tps": 5.02,
        "ttft_ms": 150,
        "total_latency_ms": 320,
        "memory_pressure_mb": 1240
      },
      "stats": {
        "mean": 0.89,
        "std": 0.06,
        "min": 0.78,
        "max": 0.95,
        "median": 0.90,
        "runs": 5,
        "confidence_95": [0.85, 0.93],
        "coefficient_of_variation": 0.067
      }
    },
    
    "artifacts": {
      "response": "Paris is the capital of France.",
      "logs": [...],
      "errors": [],
      "trace_file": "results/traces/trace_abc123.json"
    },
    
    "config": {
      "prompt_version": "v1",
      "packs_used": ["general-pack"],
      "seed": 42,
      "num_runs": 5,
      "hardware": {
        "platform": "macOS-14.5-arm64-arm-64bit",
        "processor": "arm",
        "memory_gb": 18,
        "architecture": "arm64"
      }
    },
    
    "timestamp": "2024-06-01T12:34:56.000Z",
    "git_sha": "a1b2c3d",
    "git_branch": "main"
  }
}
```

---

## Core Entities

### `Run`

The top-level container. Every evaluation produces exactly one Run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✓ | Globally unique run identifier |
| `version` | string | ✓ | Schema version (semver) |
| `model` | Model | ✓ | The model being evaluated |
| `provider` | Provider | ✓ | The provider serving the model |
| `workload` | Workload | ✓ | What was evaluated |
| `trace` | Trace | | Execution timeline (optional for bulk runs) |
| `metrics` | Metrics | ✓ | Evaluation scores and performance |
| `artifacts` | Artifacts | | Raw outputs |
| `config` | Config | ✓ | Evaluation parameters snapshot |
| `timestamp` | string | ✓ | ISO 8601 timestamp |
| `git_sha` | string | | Git commit SHA |
| `git_branch` | string | | Git branch name |

### `Model`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✓ | Model identifier (e.g., "qwen-3.5-9b-coder") |
| `provider` | string | ✓ | Provider serving this model |
| `parameters` | string | | Parameter count (e.g., "9b", "70b") |
| `quantization` | string | | Quantization level (e.g., "Q4_K_M") |
| `size_bytes` | integer | | Model file size |

### `Workload`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | ✓ | One of: `benchmark`, `prompt_pack`, `workload_project` |
| `name` | string | ✓ | Workload identifier |
| `category` | string | | Category (e.g., "reasoning", "coding", "math") |
| `version` | string | | Workload version |

### `Trace`

The execution timeline. See [Trace Schema](../packages/core/trace_schema.py) for the full Python dataclass.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trace_id` | string | ✓ | Globally unique trace identifier |
| `started_at` | string | ✓ | ISO 8601 start time |
| `completed_at` | string | ✓ | ISO 8601 completion time |
| `events` | TraceEvent[] | ✓ | Ordered event timeline |
| `metrics` | TraceMetrics | ✓ | Token-level timing metrics |
| `artifacts` | TraceArtifacts | | Raw response and logs |

### `TraceEvent`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✓ | Event identifier (unique within trace) |
| `type` | enum | ✓ | `system`, `prompt`, `token`, `tool_call`, `reasoning`, `response`, `error` |
| `label` | string | ✓ | Human-readable label |
| `detail` | string | | Extended description |
| `timing_ms` | number | ✓ | Duration of this step |
| `status` | enum | ✓ | `success`, `failure`, `pending` |
| `tool` | string | | Tool name (for tool_call events) |
| `input` | string | | Tool input |
| `output` | string | | Tool output |

### `Metrics`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scores` | object | | Arbitrary score dimensions (e.g., correctness, completeness) |
| `performance` | PerformanceMetrics | | Latency and throughput |
| `stats` | RunStats | | Statistical summary across multiple runs |

### `Artifacts`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `response` | string | | Full model response text |
| `logs` | string[] | | Execution log entries |
| `errors` | string[] | | Error messages |
| `trace_file` | string | | Path to serialized trace JSON |

### `Config`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt_version` | string | | Version of prompt template used |
| `packs_used` | string[] | | Prompt pack names |
| `seed` | integer | | Random seed |
| `num_runs` | integer | | Runs per prompt |
| `hardware` | HardwareInfo | | Hardware detection snapshot |

---

## Versioning

The Run schema uses **semantic versioning**:

- **Major**: Breaking changes to required fields or field types
- **Minor**: New optional fields, backward-compatible additions
- **Patch**: Documentation fixes, field description clarifications

Current version: `1.0.0`

---

## Serialization

Runs are serialized as JSON files:

```
results/
  models/
    qwen-3.5-9b/
      20240601_123456_run.json
      20240601_124500_run.json
  traces/
    trace_abc123.json
    trace_def456.json
  runs_index.json
```

The `runs_index.json` file provides a flat index of all runs for dashboard loading:

```json
{
  "version": "1.0.0",
  "generated_at": "2024-06-01T13:00:00.000Z",
  "runs": [
    {
      "run_id": "run_20240601_123456_qwen-3.5-9b",
      "model": "qwen-3.5-9b",
      "provider": "lm-studio",
      "workload_type": "benchmark",
      "workload_name": "mmlu_pro",
      "overall_score": 0.89,
      "timestamp": "2024-06-01T12:34:56.000Z"
    }
  ]
}
```

---

## Related implementations

| Implementation | File |
|----------------|------|
| Python `BenchmarkResult` dataclass | `apps/cli/results_schema.py` |
| Python `Trace` dataclass | `packages/core/trace_schema.py` |
| TypeScript `RunIndex` interface | `apps/dashboard/src/lib/loadResults.ts` |
| Dashboard API `/api/status` | `apps/dashboard/src/pages/api/status.ts` |
| Dashboard API `/api/traces` | `apps/dashboard/src/pages/api/traces/index.ts` |

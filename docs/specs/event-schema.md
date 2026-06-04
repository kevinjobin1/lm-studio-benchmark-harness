# Event Schema

> Canonical contract for the Model Lens event bus. Every event emitted in the system conforms to one of these types.

---

## Architecture

```
Provider calls → EventBus.emit_sync() → Consumers
                                       ├── SSE bridge (dashboard)
                                       ├── Replay writer (disk)
                                       ├── Trace capture
                                       └── Future: alerts, MCP, metrics engine
```

The event bus is **thread-safe** (`threading.Lock` on subscription/mutation, handler snapshots under lock). Events are delivered synchronously via `emit_sync()` in the benchmark execution path.

---

## Event types

### `TokenGeneratedEvent`

Emitted for **every streaming token** from a provider response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | `str` | ✓ | Model identifier (e.g. `"qwen3.5-9b"`) |
| `token` | `str` | ✓ | Raw token text |
| `index` | `int` | ✓ | 0-based token index within this completion |
| `timing_ms` | `float` | ✓ | Milliseconds since start of completion |
| `provider` | `str` | | Provider name (`"lm-studio"`, `"ollama"`, etc.) |
| `run_id` | `str` | | Correlated benchmark run ID (set by `BenchmarkSuite`) |
| `source` | `str` | | Originating component (e.g. `"provider.openai-compatible"`) |
| `id` | `str` | | Auto-generated event ID |

**Source**: `OpenAICompatibleProvider.chat_completion()` streaming path.

**Consumers**: TraceCapture, EventBusSSEServer (dashboard), EventBusReplayWriter.

### `CompletionEvent`

Emitted after a **full provider response** (success or failure).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | `str` | ✓ | Model identifier |
| `response` | `str` | ✓ | Full response text (empty on failure) |
| `tokens_used` | `int` | ✓ | Total tokens (prompt + completion) |
| `latency_ms` | `float` | ✓ | Total generation time in milliseconds |
| `ttft_ms` | `float` | ✓ | Time to first token in milliseconds |
| `tokens_per_second` | `float` | ✓ | Generation throughput |
| `provider` | `str` | | Provider name |
| `run_id` | `str` | | Correlated benchmark run ID |
| `source` | `str` | | Originating component |
| `success` | `bool` | | Whether completion succeeded |
| `error` | `str` | | Error message on failure |
| `id` | `str` | | Auto-generated event ID |

**Source**: `OpenAICompatibleProvider.chat_completion()` after success/failure.

**Consumers**: ResultsCollector, MetricsEngine, EventBusReplayWriter.

### `MetricEvent`

Emitted for any **numeric measurement** (score, latency, memory, etc.).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | ✓ | Metric name (e.g. `"general.mmlu_pro.overall_accuracy"`) |
| `value` | `float` | ✓ | Numeric value |
| `unit` | `str` | | Unit (e.g. `"ms"`, `"tokens/s"`) |
| `tags` | `Dict[str, str]` | | Arbitrary key-value metadata |
| `model` | `str` | | Model identifier |
| `run_id` | `str` | | Correlated benchmark run ID |
| `source` | `str` | | Originating component |
| `id` | `str` | | Auto-generated event ID |

**Source**: `BenchmarkSuite.run_benchmark()` (one per `BenchmarkResult`), `AppleSiliconBenchmarkV2`.

**Consumers**: Dashboard, EventBusReplayWriter, ResultsCollector.

### `RunLifecycleEvent`

Emitted at **run start, completion, or failure**.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `str` | ✓ | `"started"`, `"completed"`, or `"failed"` |
| `model` | `str` | | Model identifier |
| `provider` | `str` | | Provider name |
| `workload` | `str` | | Workload identifier (e.g. `"general/mmlu_pro"`) |
| `run_id` | `str` | | Run identifier (correlates all events for this run) |
| `source` | `str` | | Originating component |
| `duration_ms` | `float` | | Execution duration (on completed/failed) |
| `error` | `str` | | Error message (on failed) |
| `id` | `str` | | Auto-generated event ID |

**Source**: `BenchmarkSuite.run_all()` / `run_benchmark()`, `AppleSiliconBenchmarkV2`.

**Consumers**: EventBusReplayWriter (triggers session finalization), Dashboard, ResultsCollector.

### `ErrorEvent`

Emitted for **unexpected errors** anywhere in the system.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | `str` | ✓ | Human-readable error description |
| `exception` | `str` | | Exception type name |
| `stack_trace` | `str` | | Full stack trace |
| `component` | `str` | | Failing component name |
| `run_id` | `str` | | Correlated benchmark run ID |
| `source` | `str` | | Originating component |
| `severity` | `str` | | `"debug"`, `"info"`, `"warning"`, `"error"`, `"critical"` |
| `id` | `str` | | Auto-generated event ID |

**Source**: Any component on error.

**Consumers**: Dashboard, Alerts (future), EventBusReplayWriter.

### `ToolCallEvent`

Emitted when a **skill/tool is invoked** during agentic evaluation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_name` | `str` | ✓ | Name of the invoked tool/skill |
| `input_args` | `Dict[str, Any]` | ✓ | Arguments passed to the tool |
| `model` | `str` | | Model identifier |
| `run_id` | `str` | | Correlated benchmark run ID |
| `source` | `str` | | Originating component |
| `timestamp_ms` | `float` | | Timestamp in milliseconds |
| `id` | `str` | | Auto-generated event ID |

**Source**: Skill runtime during agentic benchmarks.

**Consumers**: AgenticEvaluator, TraceCapture.

---

## Event lifecycle

```
RunLifecycleEvent(status="started")          ← benchmark begins
    ├── TokenGeneratedEvent × N              ← streaming tokens
    ├── ToolCallEvent × M                    ← tool/skill invocations (agentic only)
    ├── CompletionEvent                      ← response complete
    ├── MetricEvent × K                      ← scores and measurements
    └── RunLifecycleEvent(status="completed") ← benchmark ends
           or
    RunLifecycleEvent(status="failed")        ← benchmark failed
```

---

## Subscribing to events

```python
from events import EventBus, TokenGeneratedEvent

bus = EventBus()

def on_token(event: TokenGeneratedEvent):
    print(f"{event.model} → '{event.token}' at {event.timing_ms:.1f}ms")

bus.subscribe(TokenGeneratedEvent, on_token)

# Or subscribe to all events (wildcard):
def on_any(event):
    print(f"[{type(event).__name__}] from {event.source}")

bus.subscribe_all(on_any)
```

### SSE bridge

```python
from events.sse import EventBusSSEServer
server = EventBusSSEServer(port=9090)
port = server.start()  # background thread, subscribes to default_bus
# Events are now streamed to http://localhost:9090/events
server.stop()
```

### Replay writer

```python
from events.replay import EventBusReplayWriter
writer = EventBusReplayWriter(output_dir="results/replays")
writer.start()  # subscribes to default_bus, persists to disk
# Events are now written to results/replays/<run_id>.json
writer.stop()
```

---

## Thread safety

The `EventBus` uses `threading.Lock` for all subscription mutations. `emit_sync()` snapshots handler lists under lock and iterates outside the lock, allowing concurrent emits from multiple threads (e.g., parallel benchmark execution via `ThreadPoolExecutor`).

---

## Related implementations

| Implementation | File |
|----------------|------|
| Event type definitions | `packages/events/__init__.py` |
| SSE server | `packages/events/sse.py` |
| Replay writer | `packages/events/replay.py` |
| Provider event emission | `packages/providers/openai_compatible.py` |
| Suite lifecycle emission | `packages/core/benchmark.py` |
| DevBench event emission | `apps/cli/bench_apple_silicon_v2.py` |

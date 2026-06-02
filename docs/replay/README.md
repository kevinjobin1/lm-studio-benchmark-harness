# Trace Replay

> **Status:** V2 — Planned

Trace replay lets you record and replay model execution sessions with playback controls. This is the core observability feature of Model Lens.

---

## What it captures

Each trace records the full execution timeline:

```
Run
├── Trace
│   ├── Events        ← Ordered timeline events
│   ├── Metrics       ← Latency, tokens/sec, memory at each step
│   └── Artifacts     ← Response text, logs, screenshots
```

### Events

| Timestamp | Event |
|-----------|-------|
| 00:00 | Prompt sent to model |
| 00:10 | First token received (TTFT) |
| 00:30 | Reasoning complete (if chain-of-thought) |
| 00:50 | Response complete |

### Metrics per event

- **TTFT** — Time to first token (ms)
- **Tokens/sec** — Generation throughput at each step
- **Memory** — RAM usage snapshot (MB)
- **Latency** — Cumulative execution time

### Artifacts

- Full response text
- Execution logs (stdout/stderr)
- Screenshots (future: dashboard captures)

---

## Playback controls

| Control | Description |
|---------|-------------|
| **Play** | Run the trace from start to finish |
| **Pause** | Freeze at current event |
| **Speed** | 0.5×, 1×, 2×, 4× playback speed |
| **Step** | Advance one event at a time |

---

## Side-by-side comparison

Compare two model traces side by side:

- **Token stream** — How did each model generate text?
- **Latency diff** — Where did one model spend more time?
- **Memory diff** — Which model used more RAM?
- **Output diff** — How did responses diverge?

Goal: explain **why** one model performed differently than another.

---

## Snapshot system

Save execution state as a shareable `snapshot.json`:

```json
{
  "prompt": "...",
  "model": "qwen3.5-9b-coder",
  "provider": "lm-studio",
  "metrics": {
    "ttft_ms": 210,
    "tokens_per_second": 72.3,
    "total_tokens": 145
  },
  "response": "...",
  "trace": { "events": [...] }
}
```

Shareable URL: `/runs/abc123`

---

## Data model

| Entity | Fields |
|--------|--------|
| **Trace** | `id`, `runId`, `events` |
| **Event** | `timestamp`, `type`, `data` |
| **Metric** | `ttft`, `tokensPerSecond`, `memory`, `latency` |
| **Artifact** | `response`, `logs`, `screenshots` |

---

## Current status

Trace capture and replay are planned for **V2** of Model Lens. The data model and API surface are designed but not yet implemented.

See [ROADMAP.md](../../ROADMAP.md) for the full V2 scope.

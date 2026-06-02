"""
Trace data model for execution trace capture.

Defines the schema for recording model execution timelines:
- Token-level timing (per-token text, timestamp, cumulative count)
- Event timeline (system, prompt, token, tool_call, reasoning, response, error)
- Full trace (all events, metrics, artifacts)

Mirrors the dashboard TraceTimeline component's data model (TraceRun, TraceStep)
so captured traces can be rendered directly without transformation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime


@dataclass
class TokenEvent:
    """A single token from streaming output with precise timing."""
    text: str
    index: int
    timestamp_ms: float          # ms since run start
    cumulative_tokens: int


@dataclass
class TraceEvent:
    """One event in the execution timeline.

    Matches the dashboard TraceStep type so captured traces
    can be fed directly into TraceTimeline without transformation.
    """
    id: str                      # e.g. "trace-abc123-s0"
    type: Literal["system", "prompt", "token", "tool_call", "reasoning", "response", "error"]
    label: str                   # Human-readable label
    detail: Optional[str] = None # Extended description / metadata
    timing_ms: float = 0.0       # Duration of this step
    tool: Optional[str] = None   # Tool name (for tool_call events)
    input: Optional[str] = None  # Tool input (for tool_call events)
    output: Optional[str] = None # Tool output (for tool_call events)
    status: Literal["success", "failure", "pending"] = "success"


@dataclass
class TraceMetrics:
    """Aggregate metrics for a trace run."""
    ttft_ms: float = 0.0
    tokens_per_second: float = 0.0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_latency_ms: float = 0.0
    memory_pressure_mb: float = 0.0
    # Per-token timing distribution (for latency analysis)
    token_timings_ms: List[float] = field(default_factory=list)


@dataclass
class TraceArtifacts:
    """Captured artifacts from a trace run."""
    response: str = ""
    logs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class Trace:
    """Full execution trace for a single model run.

    Can be serialized to JSON and stored alongside benchmark results.
    The dashboard loads individual trace files via /api/traces/[trace_id].
    """
    trace_id: str
    run_id: str
    model: str
    provider: str
    prompt: str
    system_prompt: Optional[str] = None
    events: List[TraceEvent] = field(default_factory=list)
    metrics: TraceMetrics = field(default_factory=TraceMetrics)
    artifacts: TraceArtifacts = field(default_factory=TraceArtifacts)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    pack: str = ""               # Prompt pack used (if any)
    hardware: Optional[Dict[str, Any]] = None  # Hardware snapshot

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict matching the dashboard TraceRun model."""
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "model": self.model,
            "provider": self.provider,
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "pack": self.pack,
            "timestamp": self.started_at,
            "totalTimeMs": self.metrics.total_latency_ms,
            "status": "completed" if not self.artifacts.errors else "failed",
            "steps": [self._event_to_step(e) for e in self.events],
            "metrics": {
                "ttft_ms": self.metrics.ttft_ms,
                "tokens_per_second": self.metrics.tokens_per_second,
                "total_tokens": self.metrics.total_tokens,
                "prompt_tokens": self.metrics.prompt_tokens,
                "completion_tokens": self.metrics.completion_tokens,
                "total_latency_ms": self.metrics.total_latency_ms,
                "memory_pressure_mb": self.metrics.memory_pressure_mb,
                "token_timings_ms": self.metrics.token_timings_ms,
            },
            "artifacts": {
                "response": self.artifacts.response,
                "logs": self.artifacts.logs,
                "errors": self.artifacts.errors,
            },
            "hardware": self.hardware,
        }

    @staticmethod
    def _event_to_step(event: TraceEvent) -> Dict[str, Any]:
        """Convert a TraceEvent to a dashboard-compatible step dict."""
        step: Dict[str, Any] = {
            "id": event.id,
            "type": event.type,
            "label": event.label,
            "timing_ms": event.timing_ms,
            "status": event.status,
        }
        if event.detail is not None:
            step["detail"] = event.detail
        if event.tool is not None:
            step["tool"] = event.tool
        if event.input is not None:
            step["input"] = event.input
        if event.output is not None:
            step["output"] = event.output
        return step

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)


__all__ = [
    "TokenEvent",
    "TraceEvent",
    "TraceMetrics",
    "TraceArtifacts",
    "Trace",
]

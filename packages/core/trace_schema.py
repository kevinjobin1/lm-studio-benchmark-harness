"""
Trace data model for execution trace capture.

Defines the schema for recording model execution timelines:
- Token-level timing (per-token text, timestamp, cumulative count)
- Event timeline (system, prompt, token, tool_call, reasoning, response, error)
- Full trace (all events, metrics, artifacts)

Mirrors the dashboard TraceTimeline component's data model (TraceRun, TraceStep)
so captured traces can be rendered directly without transformation.

Schema versioning uses semantic versioning (``MAJOR.MINOR.PATCH``):
  - MAJOR: breaking changes (field removals, type changes)
  - MINOR: new optional fields (backward-compatible additions)
  - PATCH: documentation fixes, no structural change
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


# ── Current schema version ────────────────────────────────────────

CURRENT_TRACE_VERSION = "1.0.0"


# ── Dataclasses ───────────────────────────────────────────────────


@dataclass
class TokenEvent:
    """A single token from streaming output with precise timing."""

    text: str
    index: int
    timestamp_ms: float  # ms since run start
    cumulative_tokens: int


@dataclass
class TraceEvent:
    """One event in the execution timeline.

    Matches the dashboard TraceStep type so captured traces
    can be fed directly into TraceTimeline without transformation.
    """

    id: str  # e.g. "trace-abc123-s0"
    type: Literal["system", "prompt", "token", "tool_call", "reasoning", "response", "error"]
    label: str  # Human-readable label
    detail: Optional[str] = None  # Extended description / metadata
    timing_ms: float = 0.0  # Duration of this step
    tool: Optional[str] = None  # Tool name (for tool_call events)
    input: Optional[str] = None  # Tool input (for tool_call events)
    output: Optional[str] = None  # Tool output (for tool_call events)
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

    # Schema version — for forward-compatible migrations.
    # Always write the current version when serializing; the dashboard
    # and migration tools use this to detect and upgrade older schemas.
    version: str = CURRENT_TRACE_VERSION

    system_prompt: Optional[str] = None
    events: List[TraceEvent] = field(default_factory=list)
    metrics: TraceMetrics = field(default_factory=TraceMetrics)
    artifacts: TraceArtifacts = field(default_factory=TraceArtifacts)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    pack: str = ""  # Prompt pack used (if any)
    hardware: Optional[Dict[str, Any]] = None  # Hardware snapshot

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict matching the dashboard TraceRun model."""
        return {
            "version": self.version,
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
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)

    # ── Snapshot export ────────────────────────────────────────────

    def to_snapshot(self, compress: bool = True) -> Dict[str, Any]:
        """Export a compressed, shareable snapshot of this trace.

        The snapshot is a self-contained dict that includes all trace
        data plus metadata for display.  When ``compress=True``, long
        text fields (prompt, response) are truncated to keep the
        snapshot small enough for URL embedding (base64).

        Returns:
            A dict that can be serialized to JSON, then base64-encoded
            for URL sharing.  The dict has keys:
            - snapshot_id: Short unique ID
            - version: Schema version
            - trace_id / model / provider / pack: Identifying metadata
            - prompt: Truncated prompt
            - response: Truncated response text
            - totalTimeMs / steps / metrics: Full trace data
            - hardware: Hardware snapshot (if available)
            - created_at: ISO 8601 timestamp
        """
        import hashlib

        trace_dict = self.to_dict()
        steps = trace_dict.get("steps", [])
        metrics = trace_dict.get("metrics", {})
        artifacts = trace_dict.get("artifacts", {})

        # Truncate long text fields when compressing
        prompt = self.prompt
        response_text = artifacts.get("response", "")
        if compress and len(prompt) > 200:
            prompt = prompt[:200] + "..."
        if compress and len(response_text) > 500:
            response_text = response_text[:500] + "..."

        # Generate a short snapshot ID from the trace_id hash
        snap_id = f"snap-{hashlib.sha256(self.trace_id.encode()).hexdigest()[:4]}"

        return {
            "snapshot_id": snap_id,
            "version": CURRENT_TRACE_VERSION,
            "trace_id": self.trace_id,
            "model": self.model,
            "provider": self.provider,
            "pack": self.pack,
            "prompt": prompt,
            "response": response_text,
            "totalTimeMs": metrics.get("total_latency_ms", 0),
            "metrics": {
                "ttft_ms": metrics.get("ttft_ms", 0),
                "tokens_per_second": metrics.get("tokens_per_second", 0),
                "total_tokens": metrics.get("total_tokens", 0),
            },
            "steps": steps,
            "hardware": self.hardware,
            "created_at": self.started_at,
        }

    def to_snapshot_json(self, compress: bool = True) -> str:
        """Export as JSON string (ready for base64 encoding)."""
        return json.dumps(self.to_snapshot(compress=compress), indent=None, default=str, ensure_ascii=False)

    def to_snapshot_base64(self, compress: bool = True) -> str:
        """Export as a base64-encoded, URL-safe snapshot string.

        The resulting string can be used as a query parameter for
        no-server-state sharing:

            /runs?snap=eyJzbmFwc2hvdF9pZCI6...
        """
        import base64

        json_str = self.to_snapshot_json(compress=compress)
        return base64.urlsafe_b64encode(json_str.encode()).decode()


# ── Snapshot deserialization ────────────────────────────────────────


def snapshot_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Deserialize a snapshot dict (as produced by ``Trace.to_snapshot()``)."""
    return data


def snapshot_from_base64(encoded: str) -> Dict[str, Any]:
    """Decode a base64-encoded snapshot string back to a dict."""
    import base64

    try:
        decoded = base64.urlsafe_b64decode(encoded.encode())
        return json.loads(decoded.decode())
    except Exception as exc:
        raise ValueError(f"Invalid base64 snapshot: {exc}") from exc


def snapshot_to_share_url(snapshot_data: Dict[str, Any], base_url: str = "") -> str:
    """Build a shareable URL from a snapshot dict.

    Embeds the snapshot as a base64 query parameter so no server-side
    storage is needed ("no server state" sharing).

    Returns:
        A URL like ``/runs?snap=eyJzbmFwc2hvdF9pZCI6...``
    """
    import json
    import base64

    json_str = json.dumps(snapshot_data, indent=None, default=str, ensure_ascii=False)
    encoded = base64.urlsafe_b64encode(json_str.encode()).decode()
    return f"{base_url}/runs?snap={encoded}"


__all__ = [
    "TokenEvent",
    "TraceEvent",
    "TraceMetrics",
    "TraceArtifacts",
    "Trace",
    "CURRENT_TRACE_VERSION",
    "migrate_trace",
    "snapshot_from_dict",
    "snapshot_from_base64",
    "snapshot_to_share_url",
]

# Registry of migration functions, keyed by source version.
# Each function receives the trace dict and returns it upgraded to the
# next version (or the current version if no intermediate steps exist).
_MIGRATIONS: Dict[str, Any] = {}


def migrate_trace(trace_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a trace dict from its current version to the latest schema.

    Detects the schema version from ``trace_dict["version"]``, applies
    any registered migration functions in order, and returns the
    upgraded dict.  If the version is missing, assumes ``"1.0.0"``
    (the version field was added in 1.0.0, so pre-version traces
    become 1.0.0 implicitly).

    Args:
        trace_dict: A trace dict as returned by ``Trace.to_dict()``.

    Returns:
        The migrated dict, now at ``CURRENT_TRACE_VERSION``.

    Example:
        >>> old = {"trace_id": "x", "version": "1.0.0"}
        >>> new = migrate_trace(old)
        >>> new["version"]
        '1.0.0'
    """
    version = trace_dict.get("version", "1.0.0")

    # Pre-1.0.0 traces have no version field — set it now so migration
    # callbacks always see a populated version key.
    trace_dict.setdefault("version", version)

    # Apply migrations sequentially until we reach the current version.
    # Cap iterations at len(_MIGRATIONS) + 1 to guard against
    # inadvertently infinite loops from migration functions that
    # forget to bump the version.
    for _ in range(len(_MIGRATIONS) + 1):
        version = trace_dict.get("version", "1.0.0")
        if version == CURRENT_TRACE_VERSION:
            break
        migration = _MIGRATIONS.get(version)
        if migration is None:
            # No migration path — set version and break to avoid
            # infinite loop on unknown versions
            trace_dict["version"] = CURRENT_TRACE_VERSION
            break
        trace_dict = migration(trace_dict)
    else:
        # Safeguard tripped — a migration didn't advance the version
        raise RuntimeError(
            f"Migration loop detected for trace {trace_dict.get('trace_id', 'unknown')}. "
            f"Check that every migration in _MIGRATIONS advances the version."
        )

    return trace_dict


def _register_migration(source_version: str):
    """Decorator to register a migration function for a source version."""

    def decorator(fn):
        _MIGRATIONS[source_version] = fn
        return fn

    return decorator


# ── Future migration example (uncomment when needed) ──────────────
#
# @_register_migration("1.0.0")
# def _migrate_1_0_to_1_1(trace_dict: Dict[str, Any]) -> Dict[str, Any]:
#     \"\"\"Migrate from 1.0.0 to 1.1.0.\"\"\"
#     # Example: add a new optional field
#     trace_dict.setdefault("tags", [])
#     trace_dict["version"] = "1.1.0"
#     return trace_dict


__all__ = [
    "TokenEvent",
    "TraceEvent",
    "TraceMetrics",
    "TraceArtifacts",
    "Trace",
    "CURRENT_TRACE_VERSION",
    "migrate_trace",
]

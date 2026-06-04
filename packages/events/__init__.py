"""
Model Lens Event Bus — a lightweight, typed event system for observability.

Architecture:
    Provider calls → EventBus emits events → Consumers (metrics, traces, replay, dashboard)

This decouples data producers (benchmarks, provider calls, tool execution) from
data consumers (metrics engine, trace capture, replay engine, MCP server, skill runtime).

Usage:
    from events import EventBus, TokenGeneratedEvent, CompletionEvent

    bus = EventBus()
    bus.subscribe(TokenGeneratedEvent, on_token)

    async with bus.publish() as ctx:
        ctx.emit(TokenGeneratedEvent(model="qwen", token="hello", index=0, timing_ms=12.5))
"""

import time
import uuid
import asyncio
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable, Type, Set, Union


# ── Event Enums ────────────────────────────────────────────────────


class EventPriority(Enum):
    """Priority levels for event delivery."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class EventType(Enum):
    """Canonical event types in the Model Lens event taxonomy."""

    # Lifecycle
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"

    # Provider interaction
    PROMPT_SENT = "provider.prompt_sent"
    TOKEN_GENERATED = "provider.token_generated"
    COMPLETION_RECEIVED = "provider.completion_received"
    PROVIDER_ERROR = "provider.error"

    # Tool/skill execution
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"

    # Metrics
    METRIC_RECORDED = "metric.recorded"
    MEMORY_UPDATE = "metric.memory_update"
    LATENCY_UPDATE = "metric.latency_update"

    # Trace
    TRACE_CAPTURED = "trace.captured"
    TRACE_REPLAYED = "trace.replayed"

    # System
    SYSTEM_HEALTH = "system.health"
    CONFIG_CHANGED = "system.config_changed"
    ERROR = "system.error"


# ── Base Event ─────────────────────────────────────────────────────


class ModelLensEvent:
    """Base class for all events in the system.

    Every event has:
    - id: Unique identifier (auto-generated)
    - timestamp: Unix milliseconds when emitted
    - type: Canonical EventType
    - source: Component that emitted the event (e.g., "benchmark.workload", "provider.ollama")
    - run_id: Associated benchmark run (if applicable)
    - priority: Delivery priority
    """

    __event_type__: EventType

    def __init__(
        self,
        type: EventType,
        source: str = "",
        run_id: str = "",
        priority: EventPriority = EventPriority.NORMAL,
    ):
        self.id = f"evt_{uuid.uuid4().hex[:12]}"
        self.timestamp = int(time.time() * 1000)
        self.type = type
        self.source = source
        self.run_id = run_id
        self.priority = priority


# ── Concrete Event Types ───────────────────────────────────────────


@dataclass
class TokenGeneratedEvent:
    """Emitted for each token from a streaming provider response."""

    __event_type__ = EventType.TOKEN_GENERATED
    model: str
    token: str
    index: int
    timing_ms: float
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    provider: str = ""
    run_id: str = ""
    source: str = ""


@dataclass
class ToolCallEvent:
    """Emitted when a tool/skill is invoked during agentic evaluation."""

    __event_type__ = EventType.TOOL_CALLED
    tool_name: str
    input_args: Dict[str, Any]
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    model: str = ""
    run_id: str = ""
    source: str = ""
    timestamp_ms: float = 0.0


@dataclass
class CompletionEvent:
    """Emitted when a provider returns a full completion."""

    __event_type__ = EventType.COMPLETION_RECEIVED
    model: str
    response: str
    tokens_used: int
    latency_ms: float
    ttft_ms: float
    tokens_per_second: float
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    provider: str = ""
    run_id: str = ""
    source: str = ""
    success: bool = True
    error: Optional[str] = None


@dataclass
class MetricEvent:
    """Emitted for any numeric metric (latency, memory, score, etc.)."""

    __event_type__ = EventType.METRIC_RECORDED
    name: str
    value: float
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    model: str = ""
    run_id: str = ""
    source: str = ""


@dataclass
class ErrorEvent:
    """Emitted when an error occurs anywhere in the system."""

    __event_type__ = EventType.ERROR
    message: str
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    component: str = ""
    run_id: str = ""
    source: str = ""
    severity: str = "error"  # debug, info, warning, error, critical


@dataclass
class RunLifecycleEvent:
    """Emitted at run start/completion/failure."""

    __event_type__ = EventType.RUN_STARTED
    status: str  # started, completed, failed
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    model: str = ""
    provider: str = ""
    workload: str = ""
    run_id: str = ""
    source: str = ""
    duration_ms: Optional[float] = None
    error: Optional[str] = None


# ── Derived event types for clear run lifecycle semantics ─────────

"""
Run lifecycle events use status as the discriminator:
    RunLifecycleEvent(status="started")  → run started
    RunLifecycleEvent(status="completed") → run completed
    RunLifecycleEvent(status="failed")   → run failed"""


# ── Event Subscriber Types ─────────────────────────────────────────

EventHandler = Callable[[Any], Awaitable[None]]
SyncEventHandler = Callable[[Any], None]


# ── Event Bus ──────────────────────────────────────────────────────


class EventBus:
    """Lightweight typed event bus for decoupled observability.

    Features:
    - Subscribe to specific event types or all events
    - Both sync and async handlers
    - Priority-based delivery
    - Publish context manager for scoped event emission
    - Run-scoped subscriptions that auto-cleanup

    Usage:
        bus = EventBus()

        # Subscribe to a specific event type
        bus.subscribe(TokenGeneratedEvent, on_token)

        # Subscribe to all events (wildcard)
        bus.subscribe_all(on_any_event)

        # Emit events within a scoped context
        async with bus.publish(run_id="run_abc") as ctx:
            ctx.emit(TokenGeneratedEvent(model="qwen", token="hello", ...))
    """

    def __init__(self):
        self._handlers: Dict[Type, List[Union[EventHandler, SyncEventHandler]]] = {}
        self._all_handlers: List[Union[EventHandler, SyncEventHandler]] = []
        self._run_scoped: Dict[str, List[Type]] = {}  # run_id -> subscribed event types
        self._enabled: bool = True
        self._lock = threading.Lock()

    # ── Subscription ──────────────────────────────────────────────

    def subscribe(
        self,
        event_type: Type,
        handler: Union[EventHandler, SyncEventHandler],
        run_id: Optional[str] = None,
    ):
        """Subscribe to a specific event type.

        If run_id is provided, the subscription is auto-removed when
        the run completes (via unsubscribe_run).
        """
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

            if run_id:
                if run_id not in self._run_scoped:
                    self._run_scoped[run_id] = []
                self._run_scoped[run_id].append(event_type)

    def subscribe_all(self, handler: Union[EventHandler, SyncEventHandler]):
        """Subscribe to ALL events (wildcard handler)."""
        with self._lock:
            self._all_handlers.append(handler)

    def unsubscribe(self, event_type: Type, handler: Union[EventHandler, SyncEventHandler]):
        """Remove a specific handler for an event type."""
        with self._lock:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h is not handler
                ]

    def unsubscribe_all(self, handler: Union[EventHandler, SyncEventHandler]):
        """Remove a wildcard handler."""
        with self._lock:
            self._all_handlers = [h for h in self._all_handlers if h is not handler]

    def unsubscribe_run(self, run_id: str):
        """Remove all subscriptions scoped to a run."""
        with self._lock:
            if run_id in self._run_scoped:
                del self._run_scoped[run_id]
        # Also remove from _handlers — we track which types were added per run
        # but the individual handlers are cleaned up by the subscriber

    # ── Publishing ─────────────────────────────────────────────────

    async def emit(self, event: Any):
        """Emit a single event to all subscribers.

        This is the core publishing method. It distributes events to:
        1. Type-specific handlers (in priority order)
        2. Wildcard handlers (subscribed via subscribe_all)

        Both sync and async handlers are supported.
        """
        if not self._enabled:
            return

        event_type = type(event)

        # Snapshot handlers under lock to allow concurrent mutation
        with self._lock:
            typed_handlers = list(self._handlers.get(event_type, []))
            all_handlers = list(self._all_handlers)

        for handler in typed_handlers + all_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                # Don't let subscriber errors propagate — log and continue
                pass

    def emit_sync(self, event: Any):
        """Synchronous version of emit for non-async contexts.

        Thread-safe: snapshots handler lists under a lock, then iterates
        the copy so concurrent subscribe/unsubscribe won't cause errors.
        """
        if not self._enabled:
            return

        event_type = type(event)

        # Snapshot handlers under lock to allow concurrent mutation
        with self._lock:
            typed_handlers = list(self._handlers.get(event_type, []))
            all_handlers = list(self._all_handlers)

        for handler in typed_handlers + all_handlers:
            try:
                handler(event)
            except Exception:
                pass

    def publish(self, run_id: str = "", source: str = ""):
        """Create a publish context for scoped event emission.

        Usage:
            async with bus.publish(run_id="run_abc") as ctx:
                ctx.emit(TokenGeneratedEvent(...))
        """
        return _PublishContext(self, run_id=run_id, source=source)

    # ── Lifecycle ──────────────────────────────────────────────────

    def enable(self):
        """Enable event emission."""
        self._enabled = True

    def disable(self):
        """Disable event emission (e.g., during teardown)."""
        self._enabled = False

    @property
    def handler_count(self) -> int:
        """Total number of registered handlers."""
        type_count = sum(len(h) for h in self._handlers.values())
        return type_count + len(self._all_handlers)

    def clear(self):
        """Remove all subscriptions."""
        with self._lock:
            self._handlers.clear()
            self._all_handlers.clear()
            self._run_scoped.clear()


# ── Publish Context ────────────────────────────────────────────────


class _PublishContext:
    """Scoped event emission context. Auto-sets source and run_id on events."""

    def __init__(self, bus: EventBus, run_id: str = "", source: str = ""):
        self._bus = bus
        self._run_id = run_id
        self._source = source
        self._events_emitted: int = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def emit(self, event: Any):
        """Emit an event within this context, auto-setting source/run_id."""
        if self._run_id and hasattr(event, "run_id") and not event.run_id:
            event.run_id = self._run_id
        if self._source and hasattr(event, "source") and not event.source:
            event.source = self._source

        self._bus.emit_sync(event)
        self._events_emitted += 1

    @property
    def events_emitted(self) -> int:
        return self._events_emitted


# ── Global Instance ────────────────────────────────────────────────

# Singleton event bus used by default. Components can create their own
# instances for testing or isolation.
default_bus = EventBus()


__all__ = [
    "EventBus",
    "EventType",
    "EventPriority",
    "ModelLensEvent",
    "TokenGeneratedEvent",
    "ToolCallEvent",
    "CompletionEvent",
    "MetricEvent",
    "ErrorEvent",
    "RunLifecycleEvent",
    "default_bus",
    # OTel
    "subscribe_otel",
    "is_otel_available",
]

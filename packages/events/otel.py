"""
OpenTelemetry Collector for Model Lens EventBus.

Subscribes to typed EventBus events (RunLifecycleEvent, CompletionEvent,
TokenGeneratedEvent, ToolCallEvent, MetricEvent, ErrorEvent) and converts
them into OpenTelemetry spans and metrics for export to any OTLP-compatible
backend (Jaeger, Grafana Tempo, SigNoz, Honeycomb, Datadog, etc.).

No hard dependency on ``opentelemetry-*`` packages — the import is
deferred and the subscriber is a no-op if the SDK is not installed.

Usage:
    from events.otel import OtelCollector

    collector = OtelCollector()
    collector.start()      # Subscribes to default EventBus
    # ... run benchmarks ...
    collector.stop()       # Flushes and unsubscribes

Environment variables (standard OTel env vars):
    OTEL_EXPORTER_OTLP_ENDPOINT   — OTLP receiver URL (default: "http://localhost:4317")
    OTEL_EXPORTER_OTLP_PROTOCOL   — "grpc" (default) or "http/protobuf"
    OTEL_SERVICE_NAME             — Service name (default: "model-lens")
    OTEL_ENABLED                  — Set to "1" or "true" to auto-enable (default: off)
"""

from __future__ import annotations

import os
import time
import json
import threading
from dataclasses import fields as dataclass_fields
from typing import Any, Dict, List, Optional, Set, Callable


# ── Lazy OTel imports (optional dependency) ────────────────────────

_OTEL_AVAILABLE = False
_OTEL_IMPORT_ERROR: Optional[str] = None

try:
    import opentelemetry
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

    _OTEL_AVAILABLE = True
except ImportError as _exc:
    _OTEL_IMPORT_ERROR = str(_exc)
    # Try HTTP/protobuf exporters as alternative
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        _OTEL_AVAILABLE = True
    except ImportError:
        pass

# ── Default config ─────────────────────────────────────────────────

DEFAULT_OTLP_ENDPOINT = os.environ.get(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
)
DEFAULT_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "model-lens")
OTEL_PROTOCOL = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "0").lower() in ("1", "true", "yes")


# ── Span / Metric builders ─────────────────────────────────────────


def _event_to_span_name(event_obj: Any, event_type: str) -> str:
    """Derive an OTel span name from an event."""
    if event_type == "RunLifecycleEvent":
        status = getattr(event_obj, "status", "unknown")
        workload = getattr(event_obj, "workload", "")
        return f"run.{status}" if not workload else f"run.{workload}.{status}"
    if event_type == "CompletionEvent":
        return "llm.completion"
    if event_type == "TokenGeneratedEvent":
        return "llm.token_generated"
    if event_type == "ToolCallEvent":
        tool = getattr(event_obj, "tool_name", "unknown")
        return f"tool.{tool}"
    if event_type == "ErrorEvent":
        return "system.error"
    return f"event.{event_type}"


def _event_to_attributes(event_obj: Any, event_type: str) -> Dict[str, Any]:
    """Extract OTel span attributes from an event.

    Only scalar values (str, int, float, bool) are included since OTel
    attributes do not accept arbitrary Python objects or nested structures.
    """
    attrs: Dict[str, Any] = {}
    if hasattr(event_obj, "__dataclass_fields__"):
        for f in dataclass_fields(event_obj):
            val = getattr(event_obj, f.name)
            if val is None or val == "":
                continue
            if isinstance(val, (str, int, float, bool)):
                attrs[f"event.{f.name}"] = val
    return attrs


def _event_to_metric_name(event_type: str) -> Optional[str]:
    """Map an event type to an OTel metric name, or None if not a metric."""
    mapping = {
        "CompletionEvent": "llm.completions",
        "TokenGeneratedEvent": "llm.tokens",
        "MetricEvent": None,  # MetricEvent.name is the metric name
        "ErrorEvent": "system.errors",
        "ToolCallEvent": "tool.calls",
    }
    return mapping.get(event_type)


def _event_to_metric_value(event_obj: Any, event_type: str) -> Optional[float]:
    """Extract a numeric value for OTel metrics from an event."""
    if event_type == "CompletionEvent":
        return float(getattr(event_obj, "latency_ms", 0))
    if event_type == "TokenGeneratedEvent":
        return 1.0  # Counter: one token
    if event_type == "MetricEvent":
        return float(getattr(event_obj, "value", 0))
    if event_type == "ErrorEvent":
        return 1.0
    if event_type == "ToolCallEvent":
        return 1.0
    return None


# ── OTel Collector ─────────────────────────────────────────────────


class OtelCollector:
    """Subscribes to EventBus events and exports them as OTel spans/metrics.

    Requires ``opentelemetry-api``, ``opentelemetry-sdk``, and
    ``opentelemetry-exporter-otlp`` to be installed. If they are not
    available, ``start()`` logs a warning and is a no-op — benchmark
    code does not need to check.

    Usage:
        from events import default_bus
        from events.otel import OtelCollector

        collector = OtelCollector(bus=default_bus)
        collector.start()
        # ... run benchmarks ...
        collector.stop()

    Environment variables:
        OTEL_EXPORTER_OTLP_ENDPOINT  — OTLP receiver (default: localhost:4317)
        OTEL_SERVICE_NAME            — Service name (default: "model-lens")
    """

    def __init__(
        self,
        bus: Any = None,
        endpoint: Optional[str] = None,
        service_name: Optional[str] = None,
        auto_enable: bool = False,
    ):
        self._bus = bus
        self._endpoint = endpoint or DEFAULT_OTLP_ENDPOINT
        self._service_name = service_name or DEFAULT_SERVICE_NAME
        self._auto_enable = auto_enable or OTEL_ENABLED
        self._started = False

        # OTel SDK instances (initialized in start())
        self._tracer_provider: Any = None
        self._meter_provider: Any = None
        self._tracer: Any = None
        self._meter: Any = None
        self._counters: Dict[str, Any] = {}
        self._active_spans: Dict[str, Any] = {}  # run_id -> span

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> bool:
        """Initialize OTel SDK and subscribe to the EventBus.

        Returns True if OTel is active, False if the SDK is unavailable
        or OTel is disabled.
        """
        if self._started:
            return self._started

        if not self._auto_enable and not os.environ.get("OTEL_ENABLED", ""):
            return False

        if not _OTEL_AVAILABLE:
            return False

        if self._bus is None:
            from events import default_bus

            self._bus = default_bus

        self._started = True
        self._init_sdk()
        self._subscribe()
        return True

    def stop(self) -> None:
        """Flush and shut down OTel SDK, unsubscribe from EventBus."""
        if not self._started:
            return

        # End any lingering active spans
        for run_id, span in list(self._active_spans.items()):
            try:
                span.end()
            except Exception:
                pass
        self._active_spans.clear()

        # Unsubscribe from EventBus
        if self._bus is not None:
            try:
                self._bus.unsubscribe_all(self._on_event)
            except Exception:
                pass

        # Shut down SDK providers
        try:
            if self._tracer_provider is not None:
                self._tracer_provider.shutdown()
        except Exception:
            pass
        try:
            if self._meter_provider is not None:
                self._meter_provider.shutdown()
        except Exception:
            pass

        self._started = False

    def __enter__(self) -> "OtelCollector":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()

    @property
    def is_active(self) -> bool:
        """Whether OTel is initialized and subscribed."""
        return self._started and _OTEL_AVAILABLE

    # ── SDK initialization ─────────────────────────────────────────

    def _init_sdk(self) -> None:
        """Initialize OTel TracerProvider and MeterProvider."""
        if not _OTEL_AVAILABLE:
            return

        resource = Resource.create({SERVICE_NAME: self._service_name})

        # Trace provider
        # Note: insecure/ TLS settings are resolved automatically from
        # standard OTel env vars (OTEL_EXPORTER_OTLP_INSECURE,
        # OTEL_EXPORTER_OTLP_CERTIFICATE, etc.).
        self._tracer_provider = TracerProvider(resource=resource)
        span_exporter = OTLPSpanExporter(endpoint=self._endpoint)
        span_processor = BatchSpanProcessor(span_exporter)
        self._tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(self._tracer_provider)
        self._tracer = trace.get_tracer(__name__)

        # Meter provider
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=self._endpoint),
            export_interval_millis=10_000,
        )
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(self._meter_provider)
        self._meter = metrics.get_meter(__name__)

        # Pre-create well-known counters
        if self._meter is not None:
            self._counters["completions"] = self._meter.create_counter(
                name="llm.completions",
                unit="{count}",
                description="Number of LLM completions",
            )
            self._counters["tokens"] = self._meter.create_counter(
                name="llm.tokens",
                unit="{token}",
                description="Number of generated tokens",
            )
            self._counters["errors"] = self._meter.create_counter(
                name="system.errors",
                unit="{count}",
                description="Number of errors",
            )
            self._counters["tool_calls"] = self._meter.create_counter(
                name="tool.calls",
                unit="{count}",
                description="Number of tool calls",
            )
            self._counters["latency"] = self._meter.create_histogram(
                name="llm.latency",
                unit="ms",
                description="LLM completion latency in milliseconds",
            )

    # ── EventBus subscription ──────────────────────────────────────

    def _subscribe(self) -> None:
        """Subscribe to all events on the EventBus."""
        if self._bus is None:
            return
        try:
            self._bus.subscribe_all(self._on_event)
        except Exception:
            pass

    # ── Event handler ──────────────────────────────────────────────

    def _on_event(self, event_obj: Any) -> None:
        """Called by EventBus for every emitted event.

        Converts the event to OTel spans and metrics based on its type.
        """
        if not _OTEL_AVAILABLE or not self._started:
            return

        event_type = type(event_obj).__name__
        span_name = _event_to_span_name(event_obj, event_type)
        attributes = _event_to_attributes(event_obj, event_type)

        # ── RunLifecycleEvent → manage active spans ────────────
        if event_type == "RunLifecycleEvent":
            self._handle_run_lifecycle(event_obj, span_name, attributes)
            return

        # ── CompletionEvent → create a span + record metrics ───
        if event_type == "CompletionEvent":
            self._handle_completion(event_obj, span_name, attributes)
            return

        # ── TokenGeneratedEvent → add event to active span ─────
        if event_type == "TokenGeneratedEvent":
            self._handle_token(event_obj, attributes)
            return

        # ── MetricEvent → record OTel metric ───────────────────
        if event_type == "MetricEvent":
            self._record_metric(event_obj, attributes)
            return

        # ── ErrorEvent → record counter + create error span ────
        if event_type == "ErrorEvent":
            self._handle_error(event_obj, span_name, attributes)
            return

        # ── ToolCallEvent → record counter ─────────────────────
        if event_type == "ToolCallEvent":
            self._handle_tool_call(event_obj, attributes)
            return

    # ── Per-type handlers ─────────────────────────────────────────

    def _handle_run_lifecycle(
        self, event: Any, span_name: str, attributes: Dict[str, Any]
    ) -> None:
        """Manage span lifecycle for run.start/completed/failed."""
        run_id = getattr(event, "run_id", "")
        status = getattr(event, "status", "")

        if status == "started":
            # Create a new root span for this run
            if run_id and self._tracer is not None:
                span = self._tracer.start_span(
                    name=span_name,
                    attributes=attributes,
                    kind=trace.SpanKind.INTERNAL,
                )
                self._active_spans[run_id] = span
        elif status in ("completed", "failed"):
            # End the associated span
            span = self._active_spans.pop(run_id, None)
            if span is not None:
                if status == "failed":
                    error_msg = getattr(event, "error", None)
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, error_msg or "run failed")
                    )
                if attributes:
                    span.set_attributes(attributes)

                duration = getattr(event, "duration_ms", None)
                if duration is not None:
                    span.set_attribute("run.duration_ms", duration)

                span.end()

    def _handle_completion(
        self, event: Any, span_name: str, attributes: Dict[str, Any]
    ) -> None:
        """Create an LLM completion span and record metrics."""
        run_id = getattr(event, "run_id", "")
        latency = getattr(event, "latency_ms", 0)
        tokens = getattr(event, "tokens_used", 0)
        success = getattr(event, "success", True)

        # Record metrics
        counter = self._counters.get("completions")
        if counter is not None:
            counter.add(1, attributes)

        latency_hist = self._counters.get("latency")
        if latency_hist is not None and latency > 0:
            latency_hist.record(latency, attributes)

        # Create span
        if self._tracer is not None:
            # Try to find parent span by run_id
            parent = self._active_spans.get(run_id)
            ctx = trace.set_span_in_current_context(parent) if parent else None

            if ctx:
                with self._tracer.start_as_current_span(
                    name=span_name,
                    attributes=attributes,
                    context=ctx,
                    kind=trace.SpanKind.CLIENT,
                ) as span:
                    span.set_attribute("llm.latency_ms", latency)
                    span.set_attribute("llm.tokens_used", tokens)
                    if not success:
                        error = getattr(event, "error", "completion failed")
                        span.set_status(
                            trace.Status(trace.StatusCode.ERROR, error)
                        )
            else:
                span = self._tracer.start_span(
                    name=span_name,
                    attributes=attributes,
                    kind=trace.SpanKind.CLIENT,
                )
                span.set_attribute("llm.latency_ms", latency)
                span.set_attribute("llm.tokens_used", tokens)
                if not success:
                    error = getattr(event, "error", "completion failed")
                    span.set_status(trace.Status(trace.StatusCode.ERROR, error))
                span.end()

    def _handle_token(
        self, event: Any, attributes: Dict[str, Any]
    ) -> None:
        """Record token count metric."""
        counter = self._counters.get("tokens")
        if counter is not None:
            counter.add(1, attributes)

    def _record_metric(
        self, event: Any, attributes: Dict[str, Any]
    ) -> None:
        """Record a MetricEvent as an OTel gauge/histogram."""
        metric_name = getattr(event, "name", "")
        metric_value = getattr(event, "value", 0)
        if not metric_name or not isinstance(metric_value, (int, float)):
            return

        # Create a gauge for this metric on first use
        if self._meter is not None and metric_name not in self._counters:
            try:
                self._counters[metric_name] = self._meter.create_gauge(
                    name=metric_name,
                    unit=getattr(event, "unit", ""),
                    description=f"Custom metric: {metric_name}",
                )
            except Exception:
                return

        gauge = self._counters.get(metric_name)
        if gauge is not None:
            try:
                gauge.set(metric_value, attributes)
            except Exception:
                pass

    def _handle_error(
        self, event: Any, span_name: str, attributes: Dict[str, Any]
    ) -> None:
        """Record error counter and create an error span."""
        counter = self._counters.get("errors")
        if counter is not None:
            counter.add(1, attributes)

        if self._tracer is not None:
            span = self._tracer.start_span(
                name=span_name,
                attributes=attributes,
                kind=trace.SpanKind.INTERNAL,
            )
            error_msg = getattr(event, "message", "unknown error")
            span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
            span.end()

    def _handle_tool_call(
        self, event: Any, attributes: Dict[str, Any]
    ) -> None:
        """Record tool call counter."""
        counter = self._counters.get("tool_calls")
        if counter is not None:
            counter.add(1, attributes)


# ── Convenience ────────────────────────────────────────────────────


def subscribe_otel(
    bus: Any = None,
    endpoint: Optional[str] = None,
    service_name: Optional[str] = None,
    auto_enable: bool = True,
) -> OtelCollector:
    """Create an OtelCollector, subscribe to the EventBus, and return it.

    Auto-enables by default so that the first call in a benchmark script
    is sufficient to wire up OTel exports.

    Returns the collector (which is a no-op if OTel SDK is not installed).
    """
    collector = OtelCollector(
        bus=bus,
        endpoint=endpoint,
        service_name=service_name,
        auto_enable=auto_enable,
    )
    collector.start()
    return collector


def is_otel_available() -> bool:
    """Check whether the OpenTelemetry SDK is installed (lazy import)."""
    return _OTEL_AVAILABLE


def get_otel_import_error() -> Optional[str]:
    """Get the import error message if OTel SDK is not installed."""
    return _OTEL_IMPORT_ERROR


__all__ = [
    "OtelCollector",
    "subscribe_otel",
    "is_otel_available",
    "get_otel_import_error",
]

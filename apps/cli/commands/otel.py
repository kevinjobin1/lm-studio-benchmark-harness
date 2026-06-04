"""
OpenTelemetry collector commands for modellens CLI.

Starts an OTel collector that subscribes to the EventBus and exports
spans/metrics to any OTLP-compatible backend (Jaeger, Grafana Tempo,
SigNoz, Honeycomb, Datadog, etc.).

Usage:
    # Start in foreground (auto-detects env vars)
    modellens otel serve

    # With explicit OTLP endpoint
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 modellens otel serve

    # Quick check if OTel SDK is installed
    modellens otel status
"""

import json
import os
import sys
import time
import signal
import threading

import click

from .utils import _echo


DEFAULT_OTLP_ENDPOINT = os.environ.get(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
)
DEFAULT_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "model-lens")


@click.group()
def otel():
    """
    OpenTelemetry integration.

    Exports benchmark events (spans and metrics) to any OTLP-compatible
    backend. Requires ``opentelemetry-api``, ``opentelemetry-sdk``, and
    ``opentelemetry-exporter-otlp`` to be installed.

    \b
    Environment variables:
      OTEL_EXPORTER_OTLP_ENDPOINT  — OTLP receiver URL (default: http://localhost:4317)
      OTEL_SERVICE_NAME            — Service name (default: model-lens)
      OTEL_ENABLED                 — Set to 1 to auto-wire OTel into benchmarks

    \b
    Examples:
      modellens otel status
      modellens otel serve
    """
    pass


@otel.command(name="status")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def otel_status(json_output):
    """Check if OpenTelemetry SDK is available and configured."""
    from events.otel import is_otel_available, get_otel_import_error

    available = is_otel_available()
    import_error = get_otel_import_error()
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)
    service = os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    enabled = os.environ.get("OTEL_ENABLED", "0")

    if json_output:
        click.echo(
            json.dumps(
                {
                    "otel_available": available,
                    "import_error": import_error,
                    "endpoint": endpoint,
                    "service_name": service,
                    "otel_enabled": enabled,
                    "sdk_installed": available,
                },
                indent=2,
            )
        )
        return

    _echo("")
    _echo("📡 OpenTelemetry Status", "bold blue")

    if available:
        _echo("   ✓ OTel SDK installed and available", "bold green")
    else:
        _echo(f"   ✗ OTel SDK not available", "red")
        if import_error:
            _echo(f"     {import_error}", "dim")
        _echo("", "")
        _echo("   Install with:", "dim")
        _echo("     pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp", "dim")
        _echo("")

    _echo(f"   Endpoint:    {endpoint}", "dim")
    _echo(f"   Service:     {service}", "dim")
    _echo(f"   OTEL_ENABLED: {enabled}", "dim")

    if enabled in ("1", "true", "yes"):
        _echo("   → OTel will auto-wire into benchmarks", "cyan")
    else:
        _echo("   → Set OTEL_ENABLED=1 to auto-wire into benchmarks", "dim")

    _echo("")


@otel.command(name="serve")
@click.option(
    "--endpoint",
    default=None,
    help=f"OTLP receiver URL (default: {DEFAULT_OTLP_ENDPOINT})",
)
@click.option(
    "--service-name",
    default=None,
    help=f"Service name (default: {DEFAULT_SERVICE_NAME})",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Log collector status as JSON lines to stdout",
)
def otel_serve(endpoint, service_name, json_output):
    """Start the OTel collector and forward events to an OTLP backend.

    Subscribes to the default EventBus and exports all events as
    OpenTelemetry spans and metrics to the configured OTLP endpoint.

    Runs in the foreground. Press Ctrl+C to stop.
    """
    from events import default_bus
    from events.otel import OtelCollector, is_otel_available

    if not is_otel_available():
        _echo("✗ OpenTelemetry SDK is not installed.", "red")
        _echo("")
        _echo("  Install with:", "dim")
        _echo("    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp", "dim")
        sys.exit(1)

    actual_endpoint = endpoint or DEFAULT_OTLP_ENDPOINT
    actual_service = service_name or DEFAULT_SERVICE_NAME

    if json_output:
        click.echo(
            json.dumps(
                {
                    "event": "otel_starting",
                    "endpoint": actual_endpoint,
                    "service": actual_service,
                }
            )
        )
    else:
        _echo("")
        _echo("📡 OpenTelemetry Collector", "bold blue")
        _echo(f"   Endpoint: {actual_endpoint}", "dim")
        _echo(f"   Service:  {actual_service}", "dim")
        _echo("   Press Ctrl+C to stop.", "dim")
        _echo("")

    collector = OtelCollector(
        bus=default_bus,
        endpoint=actual_endpoint,
        service_name=actual_service,
        auto_enable=True,
    )

    if not collector.start():
        _echo("✗ Failed to start OTel collector.", "red")
        sys.exit(1)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "event": "otel_started",
                    "endpoint": actual_endpoint,
                    "service": actual_service,
                }
            )
        )

    # Handle graceful shutdown
    shutdown_requested = threading.Event()

    def _handle_signal(sig, frame):
        shutdown_requested.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        while not shutdown_requested.is_set():
            time.sleep(1)
    finally:
        collector.stop()
        if json_output:
            click.echo(
                json.dumps({"event": "otel_stopped"})
            )
        else:
            _echo("\n✓ OTel collector stopped.", "bold green")


@otel.command(name="test")
@click.option(
    "--endpoint",
    default=None,
    help=f"OTLP receiver URL (default: {DEFAULT_OTLP_ENDPOINT})",
)
def otel_test(endpoint):
    """Send a single test event to verify OTel connectivity."""
    from events.otel import OtelCollector, is_otel_available

    if not is_otel_available():
        _echo("✗ OpenTelemetry SDK is not installed.", "red")
        sys.exit(1)

    actual_endpoint = endpoint or DEFAULT_OTLP_ENDPOINT
    _echo(f"🔍 Testing OTel connection to {actual_endpoint}...", "dim")

    collector = OtelCollector(
        endpoint=actual_endpoint,
        auto_enable=True,
    )

    if not collector.start():
        _echo("✗ Failed to start OTel collector.", "red")
        sys.exit(1)

    from events import RunLifecycleEvent, CompletionEvent, MetricEvent

    # Emit a test lifecycle event
    default_bus.emit_sync(
        RunLifecycleEvent(
            status="started",
            model="test-model",
            workload="otel-test",
            run_id="otel-test-run",
            source="otel.test",
        )
    )
    _echo("  ✓ Emitted RunLifecycleEvent(started)", "green")

    # Emit a test completion
    default_bus.emit_sync(
        CompletionEvent(
            model="test-model",
            response="Hello, OTel!",
            tokens_used=3,
            latency_ms=42.0,
            ttft_ms=12.0,
            tokens_per_second=71.4,
            provider="test",
            run_id="otel-test-run",
            source="otel.test",
        )
    )
    _echo("  ✓ Emitted CompletionEvent", "green")

    # Emit test metric
    default_bus.emit_sync(
        MetricEvent(
            name="test.metric",
            value=1.0,
            unit="count",
            tags={"test": "true"},
            model="test-model",
            run_id="otel-test-run",
            source="otel.test",
        )
    )
    _echo("  ✓ Emitted MetricEvent", "green")

    # End the run
    default_bus.emit_sync(
        RunLifecycleEvent(
            status="completed",
            model="test-model",
            workload="otel-test",
            run_id="otel-test-run",
            source="otel.test",
            duration_ms=42.0,
        )
    )
    _echo("  ✓ Emitted RunLifecycleEvent(completed)", "green")

    # Wait briefly for the batch export
    time.sleep(2)

    collector.stop()
    _echo("")
    _echo(f"✓ Test events sent to {actual_endpoint}. Check your OTel backend.", "bold green")

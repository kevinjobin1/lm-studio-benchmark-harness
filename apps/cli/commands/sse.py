"""
SSE command — standalone Server-Sent Events relay server.

Starts a long-running HTTP server that subscribes to the EventBus and
broadcasts all benchmark events to connected dashboard clients via SSE.

Usage:
    modellens sse serve                    # Start on port 9090
    modellens sse serve --port 9091        # Custom port
    modellens sse serve --bridge           # Also forward to Cloudflare bridge
    modellens sse serve --host 0.0.0.0     # Bind to all interfaces

The server runs until interrupted (Ctrl+C).  The dashboard auto-detects
a running local SSE server at http://localhost:9090/health and prefers
it over the Cloudflare Worker bridge for lower latency.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time

import click

# Ensure packages/ and apps/ are importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_PACKAGES_DIR = os.path.join(_PROJECT_ROOT, "packages")
if _PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _PACKAGES_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@click.group(name="sse")
def sse():
    """Standalone SSE relay server for real-time dashboard events."""
    pass


@sse.command(name="serve")
@click.option(
    "--port", "-p", type=int, default=9090, show_default=True,
    help="Port to listen on (0 = auto-assign).",
)
@click.option(
    "--host", "-h", type=str, default="127.0.0.1", show_default=True,
    help="Host to bind to.",
)
@click.option(
    "--bridge/--no-bridge", default=True, show_default=True,
    help="Forward events to the Cloudflare Worker SSE Bridge for remote dashboard access.",
)
@click.option(
    "--bridge-url",
    default=None,
    help="Cloudflare Worker SSE Bridge URL (default: MODELLENS_SSE_WORKER_URL env var).",
)
def serve(port: int, host: str, bridge: bool, bridge_url: str | None):
    """Start a standalone SSE relay server.

    Subscribes to the global EventBus and broadcasts all benchmark
    events to connected dashboard clients.  Run this as a background
    process alongside the dashboard for live event streaming.

    The dashboard auto-detects a running local SSE server and prefers
    it over the Cloudflare Worker bridge for lower latency.

    \\b
    Examples:
      modellens sse serve                          # Default: port 9090
      modellens sse serve --port 9091 --no-bridge  # Custom port, no bridge
      modellens sse serve --host 0.0.0.0           # Bind to all interfaces
    """
    from events.sse import EventBusSSEServer
    from events import default_bus

    # Resolve bridge URL
    worker_url: str | None = None
    if bridge:
        worker_url = bridge_url or os.environ.get("MODELLENS_SSE_WORKER_URL")

    # Create and start the server
    server = EventBusSSEServer(
        bus=default_bus,
        port=port,
        host=host,
        worker_url=worker_url,
        subscribe_existing=False,
    )

    actual_port = server.start()

    click.echo("")
    click.secho("⚡ Model Lens SSE Relay", fg="bright_blue", bold=True)
    click.echo(f"   Listening on  http://{host}:{actual_port}/events")
    click.echo(f"   Health check  http://{host}:{actual_port}/health")
    click.echo(f"   Connected clients: 0")

    if worker_url:
        click.secho(f"   Bridge (→ Cloudflare)  {worker_url}", fg="cyan")

    click.echo("")
    click.echo("   Press Ctrl+C to stop.")
    click.echo("")

    # Update connected client count periodically
    def _print_stats():
        last_count = 0
        while server.is_running:
            count = server.connected_clients
            if count != last_count:
                click.echo(f"\r   Connected clients: {count}", nl=False)
                last_count = count
            time.sleep(5)

    stats_thread = threading.Thread(target=_print_stats, daemon=True)
    stats_thread.start()

    # Block until interrupted
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        click.echo("\n")
        click.echo("   Shutting down...")
    finally:
        server.stop()
        click.echo("   ✓ SSE server stopped.")

"""
EventBus SSE Bridge — forwards events to connected HTTP clients via Server-Sent Events.

Provides EventBusSSEServer — a lightweight HTTP server that subscribes to an EventBus
and broadcasts every event to all connected SSE clients. Runs in a background thread
so it can be embedded inside a benchmark process.

Architecture:
    Benchmark process emits events → EventBus → EventBusSSEServer → SSE clients (dashboard)

Usage (embedded in a benchmark CLI):
    from events.sse import EventBusSSEServer

    server = EventBusSSEServer(port=9090)
    port = server.start()  # background thread, returns actual port
    print(f"SSE_PORT:{port}")
    # ... run benchmark (events are forwarded automatically) ...
    server.stop()

Usage (standalone):
    python -c "from events.sse import run_sse_server; run_sse_server(port=9090)"
"""

import json
import socket
import sys
import threading
import time
from dataclasses import fields as dataclass_fields
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional, Set, List

from events import EventBus, default_bus
from packages.logging import get_logger

logger = get_logger(__name__)


# ── SSE HTTP Handler ────────────────────────────────────────────────


class SSEHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves Server-Sent Events from the /events endpoint.

    Each connection blocks in do_GET until the client disconnects. Events
    are pushed to the connection by the EventBusSSEServer._broadcast method
    running on a different thread.
    """

    server_ref: Optional["EventBusSSEServer"] = None  # Set by server
    _write_lock: threading.Lock

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._write_lock = threading.Lock()

    # ── Route handling ─────────────────────────────────────────────

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if self.path != "/events":
            self._send_json(404, {"error": "not found"})
            return

        self._handle_sse()

    # ── SSE connection lifecycle ────────────────────────────────────

    def _handle_sse(self):
        """Establish an SSE connection and keep it open until the client disconnects."""
        # Register this connection with the server
        if self.server_ref:
            self.server_ref._connections.add(self)

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Send initial connected event
            port = getattr(self.server, "server_port", 0)
            self._sse_send({"_event_type": "_connected", "port": port})

            # Block until client disconnects — send periodic keepalives
            while not self._client_gone():
                self._keepalive()
                time.sleep(30)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            if self.server_ref:
                self.server_ref._connections.discard(self)

    # ── Wire-level helpers ──────────────────────────────────────────

    def _sse_send(self, data: Dict[str, Any]) -> None:
        """Send an unnamed SSE event with JSON data.

        Uses unnamed events (no ``event:`` line) so all events are
        delivered to the browser's ``EventSource.onmessage`` handler
        rather than requiring named ``addEventListener`` registrations.
        The event type is embedded in the data dict as ``_event_type``.
        """
        msg = f"data: {json.dumps(data)}\n\n"
        with self._write_lock:
            self.wfile.write(msg.encode("utf-8"))
            self.wfile.flush()

    def _keepalive(self) -> None:
        """Send an SSE comment line as a keepalive."""
        try:
            with self._write_lock:
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            raise

    def _client_gone(self) -> bool:
        """Check if the client has disconnected by probing the socket."""
        try:
            self.wfile.write(b"")
            return False
        except (BrokenPipeError, ConnectionResetError, OSError):
            return True

    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        """Silence the default HTTP server request logging."""
        pass  # pragma: no cover


# ── SSE Server ──────────────────────────────────────────────────────


class EventBusSSEServer:
    """Lightweight SSE server that forwards EventBus events to HTTP clients.

    Runs in a background daemon thread so it can be embedded inside a
    benchmark process.  Subscribes to *all* events on the given EventBus
    (via subscribe_all) and broadcasts them to every connected SSE client.

    Example::

        server = EventBusSSEServer(port=9090)
        port = server.start()
        ...
        server.stop()
    """

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        port: int = 9090,
        host: str = "127.0.0.1",
    ):
        self.bus = bus or default_bus
        self.port = port
        self.host = host
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._connections: Set[SSEHandler] = set()

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> int:
        """Start the SSE server in a background daemon thread.

        Returns the actual port number (may differ from `self.port` if
        the requested port was in use).
        """
        port = self._find_available_port(self.port)
        self._server = HTTPServer((self.host, port), self._make_handler())
        self.port = port

        # Subscribe to all EventBus events
        self.bus.subscribe_all(self._on_event)

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="sse-server",
        )
        self._thread.start()

        return port

    def stop(self) -> None:
        """Stop the SSE server and unsubscribe from events."""
        self.bus.unsubscribe_all(self._on_event)

        # Join all SSE connections
        for conn in list(self._connections):
            try:
                conn.wfile.close()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        self._connections.clear()

        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._thread = None

    @property
    def is_running(self) -> bool:
        """Whether the server background thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def connected_clients(self) -> int:
        """Number of currently connected SSE clients."""
        return len(self._connections)

    # ── Event broadcasting ─────────────────────────────────────────

    def _on_event(self, event_obj: Any) -> None:
        """Called by the EventBus for every emitted event.

        Serializes the event and broadcasts it to all connected SSE clients.
        Disconnected clients are automatically cleaned up.
        """
        event_type = type(event_obj).__name__
        data = self._serialize(event_obj, event_type)
        data["_event_type"] = event_type

        # Snapshot connections, then broadcast outside it
        conns: List[SSEHandler] = list(self._connections)

        for conn in conns:
            try:
                conn._sse_send(data)
            except (BrokenPipeError, ConnectionResetError):
                self._connections.discard(conn)

    # ── Serialization ──────────────────────────────────────────────

    def _serialize(self, event_obj: Any, event_type: str) -> Dict[str, Any]:
        """Convert an event object to a JSON-serializable dict.

        Handles Python dataclass events (TokenGeneratedEvent, CompletionEvent,
        MetricEvent, ErrorEvent, RunLifecycleEvent), ModelLensEvent subclasses,
        and arbitrary objects with __dict__.
        """
        data: Dict[str, Any] = {}

        # Dataclass events
        if hasattr(event_obj, "__dataclass_fields__"):
            for f in dataclass_fields(event_obj):
                val = getattr(event_obj, f.name)
                data[f.name] = _serialize_value(val)
            return data

        # ModelLensEvent base class (checked via __event_type__ sentinel)
        if hasattr(event_obj, "__event_type__"):
            for attr in ("id", "timestamp", "type", "source", "run_id", "priority"):
                if hasattr(event_obj, attr):
                    data[attr] = _serialize_value(getattr(event_obj, attr))
            return data

        # Fallback: try __dict__
        if hasattr(event_obj, "__dict__"):
            for key, val in event_obj.__dict__.items():
                data[key] = _serialize_value(val)
        else:
            data["message"] = str(event_obj)

        return data

    # ── Internal helpers ───────────────────────────────────────────

    def _find_available_port(self, preferred: int) -> int:
        """Find an available TCP port starting from the preferred one.

        When ``preferred`` is 0, the OS assigns a free port and the actual
        port number is read back from the socket before releasing it.
        """
        port = preferred
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.bind((self.host, port))
                if preferred == 0:
                    port = sock.getsockname()[1]
                sock.close()
                return port
            except OSError:
                port += 1

    def _make_handler(self):
        """Create a handler class bound to this server instance.

        Uses post-definition attribute assignment to avoid Python's
        class-body closure scoping issue where ``name = name`` on the
        same line causes ``NameError``.
        """

        class BoundHandler(SSEHandler):
            pass

        BoundHandler.server_ref = self
        return BoundHandler


# ── Serialisation helpers ───────────────────────────────────────────


def _serialize_value(val: Any) -> Any:
    """Recursively serialise a value for JSON output."""
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_serialize_value(v) for v in val]
    if hasattr(val, "__dataclass_fields__"):
        return {f.name: _serialize_value(getattr(val, f.name)) for f in dataclass_fields(val)}
    # Primitives, None, etc. — fine as-is
    return val


# ── Standalone runner ────────────────────────────────────────────────


def run_sse_server(port: int = 9090, host: str = "127.0.0.1") -> EventBusSSEServer:
    """Start an SSE server on the default (global) EventBus and block forever.

    This is the entry point for running the SSE server as a standalone process::

        python -c "from events.sse import run_sse_server; run_sse_server()"

    Returns the server instance (useful for testing).
    """
    server = EventBusSSEServer(bus=default_bus, port=port, host=host)
    actual_port = server.start()
    logger.info("Model Lens SSE server started on http://%s:%s/events", host, actual_port)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()
    return server


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Model Lens SSE event bridge")
    parser.add_argument("--port", type=int, default=9090, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    run_sse_server(port=args.port, host=args.host)

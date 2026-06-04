"""E2E test: events forwarded via EventBusSSEServer → live SSE Bridge Worker."""
import json
import sys
import threading
import time
import urllib.request

sys.path.insert(0, "/Users/kjobin/Developer/model-lens/packages")

from events import EventBus, TokenGeneratedEvent, CompletionEvent, MetricEvent, ErrorEvent
from events.sse import EventBusSSEServer

BRIDGE_URL = "https://modellens-sse-bridge.kevin-jobin-1.workers.dev"

def _req(url, **kw):
    req = urllib.request.Request(url, **kw)
    req.add_header("User-Agent", "modellens/0.1")
    return urllib.request.urlopen(req, timeout=10)

print("=== E2E SSE Bridge Test ===")
print(f"Bridge: {BRIDGE_URL}")
print()

# ── 1. Health ────────────────────────────────────────────────────
resp = _req(f"{BRIDGE_URL}/health")
health = json.loads(resp.read())
print(f"1. Health: {health['status']}, connections: {health['connections']}")
print()

# ── 2a. Quick direct POST test ───────────────────────────────────
print("2a. Direct POST test...")
post_resp = _req(
    f"{BRIDGE_URL}/events",
    data=json.dumps({"_event_type": "DirectTest", "msg": "pre-check"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
direct = json.loads(post_resp.read())
print(f"   Direct POST: {direct}")
assert direct["ok"], f"Direct POST failed: {direct}"
print()

# ── 2b. Batch forward via EventBus → _forward_to_worker → POST ──
bus = EventBus()
server = EventBusSSEServer(bus=bus, worker_url=BRIDGE_URL)
bus.subscribe_all(server._on_event)
print(f"2. Pool ready (max_workers={server._worker_forwarder._max_workers})")

events = [
    TokenGeneratedEvent(model="e2e", token="Hello", index=0, timing_ms=12.5,
                        run_id="e2e-001", source="e2e-test"),
    TokenGeneratedEvent(model="e2e", token="world", index=1, timing_ms=8.2,
                        run_id="e2e-001", source="e2e-test"),
    CompletionEvent(model="e2e", response="Hello world", tokens_used=2,
                    latency_ms=45.0, ttft_ms=25.0, tokens_per_second=80.0,
                    run_id="e2e-001", source="e2e-test", success=True),
    MetricEvent(name="e2e.score", value=0.95, model="e2e",
                run_id="e2e-001", source="e2e-test"),
    ErrorEvent(message="Intentional test error", component="e2e", severity="warning"),
]

for event in events:
    bus.emit_sync(event)
server._worker_forwarder.shutdown(wait=True)
print(f"   {len(events)} events forwarded via _forward_to_worker")
print()

# ── 3. Open SSE, receive _connected, then emit+receive via DO ────
print("3. Opening SSE stream...")
req = urllib.request.Request(f"{BRIDGE_URL}/events")
req.add_header("User-Agent", "modellens/0.1")
resp = urllib.request.urlopen(req, timeout=60)

line = resp.readline().decode("utf-8", errors="replace").strip()
connected_data = json.loads(line[5:].strip())
assert connected_data["_event_type"] == "_connected", f"Expected _connected, got {connected_data}"
print(f"   ← _connected (id={connected_data.get('connection_id', '?')[:8]}...)")
resp.readline()  # blank separator line

# Emit via a background thread using _forward_to_worker path.
# NOTE: subscribe manually (start() would also start a local HTTP server
# which we don't need for forwarding-only operation).
captured: list[dict] = []
bus2 = EventBus()
server2 = EventBusSSEServer(bus=bus2, worker_url=BRIDGE_URL)
bus2.subscribe_all(server2._on_event)  # required for _forward_to_worker to fire

def emit_from_bg():
    time.sleep(1)
    bus2.emit_sync(TokenGeneratedEvent(
        model="e2e-verify", token="verification-ping", index=0,
        timing_ms=1.0, run_id="e2e-002", source="e2e",
    ))
    server2._worker_forwarder.shutdown(wait=True)
    print("   [bg] Event POSTed via _forward_to_worker")

threading.Thread(target=emit_from_bg, daemon=True).start()

# Read the SSE stream until we get the verification event.
# Loop to handle keepalives, blank lines, and late keepalives from
# previous alarm cycles on the DO.
import socket
socket.setdefaulttimeout(12)
try:
    deadline = time.time() + 10
    while time.time() < deadline:
        line = resp.readline().decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":"):
            continue  # blank line or keepalive comment
        if line.startswith("data:"):
            event_data = json.loads(line[5:].strip())
            etype = event_data.get("_event_type", "?")
            print(f"   ← {etype}: model={event_data.get('model', '?')}, "
                  f"token={event_data.get('token', '?')}")
            if etype == "_connected":
                continue  # late _connected from a reconnection
            assert etype == "TokenGeneratedEvent", f"Expected TokenGeneratedEvent, got {etype}"
            assert event_data["model"] == "e2e-verify"
            assert event_data["token"] == "verification-ping"
            captured.append(event_data)
            break
except socket.timeout:
    pass
finally:
    socket.setdefaulttimeout(None)

resp.close()
server.stop()
server2.stop()

# ── 4. Results ───────────────────────────────────────────────────
resp = _req(f"{BRIDGE_URL}/health")
health = json.loads(resp.read())
print(f"\n4. Final health: {health['status']}, connections: {health['connections']}")
print()

if captured:
    print("✓ E2E test PASSED — event forwarded and received via SSE!")
else:
    print("✗ E2E test FAILED — no verification event received from SSE stream")
    sys.exit(1)

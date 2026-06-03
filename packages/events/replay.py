"""
EventBus Replay Writer — persists events to JSON files for historical replay.

Subscribes to *all* events on an EventBus and writes them to structured
replay files in the results/replays/ directory.  Each logical run (tracked
by ``run_id``) gets its own replay file so the dashboard can load and replay
the exact event sequence from a previous benchmark or workload evaluation.

Architecture:
    Benchmark emits events → EventBus → EventBusReplayWriter → results/replays/

Usage (embedded in a benchmark CLI):
    from events.replay import EventBusReplayWriter, run_replay_writer

    writer = EventBusReplayWriter(output_dir="results/replays")
    writer.start()
    # ... run benchmark (events are persisted automatically) ...
    writer.stop()

Or as a context manager:

    with EventBusReplayWriter() as writer:
        ...
"""

import json
import os
import threading
import time
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from events import EventBus, default_bus


# ── Serialization helpers (shared logic with sse.py) ──────────────


def _serialize_value(val: Any) -> Any:
    """Recursively serialise a value for JSON output."""
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_serialize_value(v) for v in val]
    if hasattr(val, "__dataclass_fields__"):
        return {
            f.name: _serialize_value(getattr(val, f.name))
            for f in dataclass_fields(val)
        }
    return val


def _serialize_event(event_obj: Any, event_type: str) -> Dict[str, Any]:
    """Convert an event object to a JSON-serializable dict.

    Handles Python dataclass events (TokenGeneratedEvent, CompletionEvent,
    MetricEvent, ErrorEvent, RunLifecycleEvent), ModelLensEvent subclasses,
    and arbitrary objects with __dict__.
    """
    data: Dict[str, Any] = {"_event_type": event_type}

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


# ── Session tracker ───────────────────────────────────────────────


class _ReplaySession:
    """Tracks accumulated events for a single run session."""

    __slots__ = ("run_id", "model", "workload", "provider", "started_at", "events")

    def __init__(
        self,
        run_id: str,
        model: str = "",
        workload: str = "",
        provider: str = "",
    ):
        self.run_id = run_id
        self.model = model
        self.workload = workload
        self.provider = provider
        self.started_at: Optional[str] = None
        self.events: List[Dict[str, Any]] = []

    @property
    def event_count(self) -> int:
        return len(self.events)

    def to_replay_data(self) -> Dict[str, Any]:
        """Serialize the full session to a replay JSON object."""
        return {
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "model": self.model,
            "workload": self.workload,
            "provider": self.provider,
            "started_at": self.started_at,
            "event_count": self.event_count,
            "events": self.events,
        }

    def to_index_entry(self, filename: str) -> Dict[str, Any]:
        """Serialize a lightweight index entry for this session."""
        return {
            "run_id": self.run_id,
            "model": self.model,
            "workload": self.workload,
            "provider": self.provider,
            "started_at": self.started_at,
            "event_count": self.event_count,
            "file": filename,
        }


# ── Replay Writer ─────────────────────────────────────────────────


class EventBusReplayWriter:
    """Subscribes to all EventBus events and persists them as replay files.

    Each logical run (identified by ``run_id`` on events) gets its own
    replay file saved to the output directory.  When a
    ``RunLifecycleEvent(status="completed"|"failed")`` is seen, the
    corresponding session is finalised and written to disk immediately.

    Example::

        writer = EventBusReplayWriter(output_dir="results/replays")
        writer.start()
        # ... run benchmark ...
        writer.stop()
    """

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        output_dir: str = "results/replays",
    ):
        self.bus = bus or default_bus
        self.output_dir = Path(output_dir)
        self._lock = threading.Lock()
        self._sessions: Dict[str, _ReplaySession] = {}
        self._closed_run_ids: Set[str] = set()
        self._started: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        """Subscribe to all EventBus events and begin collecting."""
        if self._started:
            return
        self.bus.subscribe_all(self._on_event)
        self._started = True

    def stop(self) -> None:
        """Unsubscribe from events and flush any remaining sessions."""
        self.bus.unsubscribe_all(self._on_event)
        self._started = False
        self._flush_all()

    def __enter__(self) -> "EventBusReplayWriter":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()

    # ── Event handler ─────────────────────────────────────────────

    def _on_event(self, event_obj: Any) -> None:
        """Called by the EventBus for every emitted event."""
        event_type = type(event_obj).__name__
        data = _serialize_event(event_obj, event_type)

        # Determine which session this event belongs to
        run_id = getattr(event_obj, "run_id", None) or "default"
        model = getattr(event_obj, "model", "") or ""
        provider = getattr(event_obj, "provider", "") or ""

        with self._lock:
            # If this run_id was already finalised, skip
            if run_id in self._closed_run_ids:
                return

            # Get or create session
            session = self._sessions.get(run_id)
            if session is None:
                workload = getattr(event_obj, "workload", "") or ""
                session = _ReplaySession(run_id, model, workload, provider)
                self._sessions[run_id] = session

            # Set started_at from the first event timestamp
            if session.started_at is None:
                ts = getattr(event_obj, "timestamp", None)
                if ts:
                    if isinstance(ts, (int, float)):
                        session.started_at = datetime.fromtimestamp(
                            ts / 1000, tz=timezone.utc
                        ).isoformat()
                    else:
                        session.started_at = str(ts)
                else:
                    session.started_at = datetime.now(timezone.utc).isoformat()

            # Update model/provider if not yet known
            if not session.model and model:
                session.model = model
            if not session.provider and provider:
                session.provider = provider

            # Append the event
            session.events.append(data)

            # If this is a terminal lifecycle event, finalise the session
            if event_type == "RunLifecycleEvent":
                status = getattr(event_obj, "status", "")
                if status in ("completed", "failed"):
                    self._finalise_session(run_id)

    # ── Session finalisation ──────────────────────────────────────

    def _finalise_session(self, run_id: str) -> None:
        """Write a session to disk and remove from active sessions."""
        session = self._sessions.pop(run_id, None)
        if session is None:
            return
        self._closed_run_ids.add(run_id)

        # Build the replay file
        replay_data = session.to_replay_data()
        filename = f"{_sanitize_filename(run_id)}.json"
        file_path = self.output_dir / filename

        # Write atomically via temp file
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(replay_data, f, indent=2, default=str)
            os.replace(tmp_path, file_path)
        except Exception:
            # Clean up temp file on failure
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

        # Update the index
        self._update_index(session, filename)

    def _flush_all(self) -> None:
        """Finalise any remaining in-flight sessions."""
        with self._lock:
            for run_id in list(self._sessions.keys()):
                self._finalise_session(run_id)

    # ── Index management ──────────────────────────────────────────

    def _update_index(self, session: _ReplaySession, filename: str) -> None:
        """Update the replay index file with a new entry."""
        index_path = self.output_dir / "index.json"
        index: Dict[str, Any] = {"version": "1.0.0", "replays": []}

        # Load existing index
        if index_path.exists():
            try:
                with open(index_path) as f:
                    existing = json.load(f)
                    index["replays"] = existing.get("replays", [])
            except Exception:
                pass

        # Replace entry if run_id already exists, otherwise append
        entry = session.to_index_entry(filename)
        index["replays"] = [
            e for e in index["replays"]
            if e.get("run_id") != session.run_id
        ]
        index["replays"].append(entry)
        index["generated_at"] = datetime.now(timezone.utc).isoformat()
        index["total_replays"] = len(index["replays"])

        # Write atomically
        tmp_path = index_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(index, f, indent=2, default=str)
            os.replace(tmp_path, index_path)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    # ── Query helpers ─────────────────────────────────────────────

    @property
    def active_sessions(self) -> int:
        """Number of in-flight sessions (not yet written to disk)."""
        with self._lock:
            return len(self._sessions)

    @property
    def total_replays(self) -> int:
        """Total number of replay files written this session."""
        with self._lock:
            return len(self._closed_run_ids)


# ── Helpers ───────────────────────────────────────────────────────


def _sanitize_filename(name: str) -> str:
    """Replace characters that are invalid in filenames."""
    sanitized = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    return sanitized or "replay"


# ── Standalone runner ─────────────────────────────────────────────


def run_replay_writer(
    output_dir: str = "results/replays",
) -> EventBusReplayWriter:
    """Start a replay writer on the default EventBus and block forever.

    This is the entry point for running the replay writer as a standalone
    process::

        python -c "from events.replay import run_replay_writer; run_replay_writer()"
    """
    writer = EventBusReplayWriter(bus=default_bus, output_dir=output_dir)
    writer.start()
    print(
        f"Model Lens replay writer started → {writer.output_dir}/",
        flush=True,
    )
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        writer.stop()
    return writer


# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Model Lens EventBus replay writer")
    parser.add_argument(
        "--output-dir",
        default="results/replays",
        help="Directory for replay files (default: results/replays)",
    )
    args = parser.parse_args()

    run_replay_writer(output_dir=args.output_dir)

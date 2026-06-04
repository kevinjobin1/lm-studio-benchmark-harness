"""
TraceCapture — wraps provider chat_completion calls to record
execution traces with token-level timing.

Usage:
    capture = TraceCapture()
    with capture.run(model="qwen3.5-9b-coder", prompt="...", provider="lm-studio"):
        response_text, metrics = client.chat_completion(messages, stream=True)
        capture.record_token(token_text, token_index)

    trace = capture.finish(response_text, metrics)
    trace.to_json()  # or trace.to_dict() for the dashboard
"""

import time
import uuid
from typing import Dict, List, Optional, Generator, Any
from contextlib import contextmanager

from packages.logging import get_logger
from .trace_schema import (
    Trace,
    TraceEvent,
    TraceMetrics,
    TraceArtifacts,
)

logger = get_logger(__name__)


class TraceCapture:
    """Wraps a provider call to record execution traces.

    Use as a context manager or call start()/finish() manually.
    """

    def __init__(self):
        self._trace: Optional[Trace] = None
        self._start_time: float = 0.0
        self._first_token_time: Optional[float] = None
        self._token_count: int = 0
        self._events: List[TraceEvent] = []
        self._token_timings: List[float] = []  # inter-token gaps in ms
        self._last_token_time: float = 0.0
        self._memory_samples: List[float] = []

    # ── Context manager ──────────────────────────────────────────

    @contextmanager
    def run(
        self,
        model: str,
        prompt: str,
        provider: str = "unknown",
        system_prompt: Optional[str] = None,
        run_id: Optional[str] = None,
        pack: str = "",
        hardware: Optional[Dict[str, Any]] = None,
    ):
        """Context manager that starts a trace and finishes it on exit.

        Usage:
            with capture.run(model="qwen", prompt="...", provider="lm-studio"):
                response, metrics = client.chat_completion(messages, stream=True)
                for chunk in stream:
                    capture.record_token(chunk.text, chunk.index)
        """
        self.start(
            model=model,
            prompt=prompt,
            provider=provider,
            system_prompt=system_prompt,
            run_id=run_id,
            pack=pack,
            hardware=hardware,
        )
        try:
            yield self
        except Exception as e:
            self.record_error(f"Trace failed: {e}")
            raise
        finally:
            # Auto-finish if not already done
            if self._trace is not None and not self._trace.completed_at:
                self.finish("", None)

    # ── Lifecycle ────────────────────────────────────────────────

    def start(
        self,
        model: str,
        prompt: str,
        provider: str = "unknown",
        system_prompt: Optional[str] = None,
        run_id: Optional[str] = None,
        pack: str = "",
        hardware: Optional[Dict[str, Any]] = None,
    ):
        """Begin a new trace. Call before the provider call."""
        self._start_time = time.time()
        self._first_token_time = None
        self._token_count = 0
        self._events = []
        self._token_timings = []
        self._last_token_time = self._start_time

        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        effective_run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"

        self._trace = Trace(
            trace_id=trace_id,
            run_id=effective_run_id,
            model=model,
            provider=provider,
            prompt=prompt,
            system_prompt=system_prompt,
            pack=pack,
            hardware=hardware,
        )

        # Record system event (always first)
        sys_detail = f"Provider: {provider}. "
        if system_prompt:
            sys_detail += f"System: {system_prompt[:200]}"
        else:
            sys_detail += "Default system prompt."

        self._add_event(
            event_type="system",
            label="System Instruction",
            detail=sys_detail,
            timing_ms=0.0,
        )

        # Record prompt event
        self._add_event(
            event_type="prompt",
            label="Prompt Sent",
            detail=prompt[:500] + ("..." if len(prompt) > 500 else ""),
            timing_ms=0.0,
        )

    def record_token(self, text: str, index: int):
        """Record a single token from the streaming response.

        Call this for each chunk in the streaming loop.
        """
        now = time.time()
        if self._first_token_time is None:
            self._first_token_time = now

        inter_token_ms = (now - self._last_token_time) * 1000
        self._token_timings.append(inter_token_ms)
        self._last_token_time = now

        self._token_count += 1

    def record_error(self, message: str):
        """Record an error that occurred during execution."""
        self._add_event(
            event_type="error",
            label="Execution Error",
            detail=message,
            timing_ms=0.0,
            status="failure",
        )

    def finish(
        self,
        response_text: str,
        metrics: Optional[Any] = None,  # APICallMetrics or similar
    ) -> Trace:
        """Complete the trace with the final response and metrics.

        Returns the finished Trace object.
        """
        if self._trace is None:
            raise RuntimeError("TraceCapture.finish() called before start()")

        total_ms = (time.time() - self._start_time) * 1000
        ttft_ms = (
            (self._first_token_time - self._start_time) * 1000
            if self._first_token_time
            else total_ms
        )

        # Extract metrics from the provider's metrics object
        tokens_per_second = 0.0
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0

        if metrics is not None:
            tokens_per_second = getattr(metrics, "tokens_per_second", 0.0)
            total_tokens = getattr(metrics, "total_tokens", 0)
            prompt_tokens = getattr(metrics, "prompt_tokens", 0)
            completion_tokens = getattr(metrics, "completion_tokens", 0)

        # Compute tokens/sec from trace data if no metrics provided
        if tokens_per_second == 0.0 and self._token_count > 0:
            gen_time_s = (total_ms - ttft_ms) / 1000
            if gen_time_s > 0:
                tokens_per_second = self._token_count / gen_time_s

        # Try to get memory pressure
        memory_pressure_mb = 0.0
        try:
            import psutil
            process = psutil.Process()
            memory_pressure_mb = process.memory_info().rss / 1024 / 1024
        except (ImportError, ModuleNotFoundError):
            pass  # psutil not installed
        except Exception as e:
            logger.debug("Could not capture memory pressure: %s", e)

        # Record reasoning event (aggregate analysis)
        tps_display = f"{tokens_per_second:.1f}" if tokens_per_second > 0 else "N/A"
        self._add_event(
            event_type="reasoning",
            label="Generation Analysis",
            detail=(
                f"TTFT: {ttft_ms:.1f}ms · "
                f"Tokens/sec: {tps_display} · "
                f"Total tokens: {self._token_count} · "
                f"Memory: {memory_pressure_mb:.0f}MB"
            ),
            timing_ms=max(0, total_ms * 0.05),  # ~5% of total time
        )

        # Record response event
        response_preview = response_text[:300] + (
            "..." if len(response_text) > 300 else ""
        )
        self._add_event(
            event_type="response",
            label="Response Complete",
            detail=response_preview,
            timing_ms=max(0, total_ms * 0.6),  # ~60% of total time
        )

        # Populate trace
        self._trace.events = self._events
        self._trace.metrics = TraceMetrics(
            ttft_ms=ttft_ms,
            tokens_per_second=tokens_per_second,
            total_tokens=total_tokens or self._token_count,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens or self._token_count,
            total_latency_ms=total_ms,
            memory_pressure_mb=memory_pressure_mb,
            token_timings_ms=self._token_timings,
        )
        self._trace.artifacts = TraceArtifacts(
            response=response_text,
        )
        self._trace.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")

        return self._trace

    # ── Helpers ──────────────────────────────────────────────────

    def _add_event(
        self,
        event_type: str,
        label: str,
        detail: Optional[str] = None,
        timing_ms: float = 0.0,
        status: str = "success",
        tool: Optional[str] = None,
        input_data: Optional[str] = None,
    ):
        event_id = f"{self._trace.trace_id}-e{len(self._events)}" if self._trace else f"evt_{len(self._events)}"
        self._events.append(
            TraceEvent(
                id=event_id,
                type=event_type,  # type: ignore[arg-type]
                label=label,
                detail=detail,
                timing_ms=timing_ms,
                tool=tool,
                input=input_data,
                status=status,  # type: ignore[arg-type]
            )
        )

    @property
    def trace(self) -> Optional[Trace]:
        """Get the current trace (incomplete until finish() is called)."""
        return self._trace

    @property
    def token_count(self) -> int:
        """Number of tokens recorded so far."""
        return self._token_count


def wrap_stream(
    stream: Any,
    capture: TraceCapture,
) -> Generator[Any, None, None]:
    """Wrap a streaming response to automatically record tokens.

    Usage:
        stream = client.chat.completions.create(..., stream=True)
        for chunk in wrap_stream(stream, capture):
            if chunk.choices[0].delta.content:
                ...
    """
    token_index = 0
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            capture.record_token(text, token_index)
            token_index += 1
        yield chunk


__all__ = ["TraceCapture", "wrap_stream"]

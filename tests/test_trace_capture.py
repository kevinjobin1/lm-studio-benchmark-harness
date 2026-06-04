"""
Tests for trace capture (V2).

Run with: python3 -m pytest tests/test_trace_capture.py -v
"""

import json
import pytest
from core.trace_schema import (
    TokenEvent,
    TraceEvent,
    TraceMetrics,
    TraceArtifacts,
    Trace,
)
from core.trace_capture import TraceCapture, wrap_stream


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def capture():
    return TraceCapture()


# ── Trace Data Model ──────────────────────────────────────────


class TestTokenEvent:
    def test_creation(self):
        tok = TokenEvent(text="hello", index=0, timestamp_ms=42.0, cumulative_tokens=1)
        assert tok.text == "hello"
        assert tok.index == 0
        assert tok.timestamp_ms == 42.0
        assert tok.cumulative_tokens == 1


class TestTraceEvent:
    def test_minimal(self):
        evt = TraceEvent(id="e1", type="system", label="System Instruction", status="success")
        assert evt.id == "e1"
        assert evt.type == "system"
        assert evt.detail is None

    def test_with_tool_call(self):
        evt = TraceEvent(
            id="e2",
            type="tool_call",
            label="Calling: grep",
            tool="file_search",
            input="cache.set",
            timing_ms=18.0,
            status="success",
        )
        assert evt.tool == "file_search"
        assert evt.input == "cache.set"


class TestTrace:
    def test_creation(self):
        trace = Trace(
            trace_id="trace-abc",
            run_id="run-xyz",
            model="test-model",
            provider="lm-studio",
            prompt="What is 2+2?",
        )
        assert trace.trace_id == "trace-abc"
        assert trace.events == []

    def test_to_dict_matches_dashboard_format(self, capture):
        """The to_dict() output should be consumable by the dashboard TraceRun model."""
        capture.start(model="test-model", prompt="What is 2+2?", provider="test")
        capture.record_token("Hello", 0)
        capture.record_token(" world", 1)
        trace = capture.finish("Hello world", None)

        d = trace.to_dict()

        # Top-level fields matching dashboard TraceRun
        assert "trace_id" in d
        assert "run_id" in d
        assert d["model"] == "test-model"
        assert d["provider"] == "test"
        assert d["prompt"] == "What is 2+2?"
        assert "totalTimeMs" in d
        assert d["totalTimeMs"] > 0
        assert d["status"] == "completed"

        # Steps array matching dashboard TraceStep[]
        assert "steps" in d
        assert isinstance(d["steps"], list)
        assert len(d["steps"]) >= 4  # system, prompt, reasoning, response at minimum

        # First step should be system
        assert d["steps"][0]["type"] == "system"
        assert d["steps"][0]["label"] == "System Instruction"

        # Last step should be response
        assert d["steps"][-1]["type"] == "response"

        # Metrics object
        assert "metrics" in d
        assert "ttft_ms" in d["metrics"]
        assert "tokens_per_second" in d["metrics"]
        assert "total_latency_ms" in d["metrics"]

    def test_to_json_produces_valid_json(self, capture):
        capture.start(model="m", prompt="p", provider="x")
        trace = capture.finish("response", None)
        json_str = trace.to_json()
        parsed = json.loads(json_str)
        assert parsed["model"] == "m"
        assert parsed["prompt"] == "p"

    def test_serialization_roundtrip_via_json(self, capture):
        """Trace serialized to JSON should be loadable back as dict."""
        capture.start(model="roundtrip-model", prompt="Hello?", provider="test")
        capture.record_token("Hi", 0)
        trace = capture.finish("Hi", None)

        json_str = trace.to_json()
        reloaded = json.loads(json_str)

        assert reloaded["trace_id"] == trace.trace_id
        assert reloaded["run_id"] == trace.run_id
        assert reloaded["model"] == "roundtrip-model"
        assert len(reloaded["steps"]) == len(trace.events)


# ── TraceCapture Lifecycle ────────────────────────────────────


class TestTraceCaptureLifecycle:
    def test_start_creates_trace(self, capture):
        capture.start(model="m1", prompt="p1", provider="test")
        assert capture.trace is not None
        assert capture.trace.model == "m1"
        assert capture.trace.prompt == "p1"
        assert capture.trace.provider == "test"
        # Should have system + prompt events
        assert len(capture.trace.events) == 0  # events initialized but not populated yet
        # Actually events are stored in _events until finish()

    def test_finish_populates_all_fields(self, capture):
        capture.start(model="m2", prompt="p2", provider="test")
        capture.record_token("a", 0)
        capture.record_token("b", 1)
        trace = capture.finish("ab", None)

        assert trace.events is not None
        assert len(trace.events) >= 4  # system, prompt, reasoning, response
        assert trace.metrics is not None
        assert trace.metrics.ttft_ms >= 0
        assert trace.artifacts is not None
        assert trace.artifacts.response == "ab"
        assert trace.completed_at != ""

    def test_finish_raises_without_start(self, capture):
        with pytest.raises(RuntimeError, match="before start"):
            capture.finish("", None)

    def test_token_count(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        assert capture.token_count == 0
        capture.record_token("x", 0)
        capture.record_token("y", 1)
        capture.record_token("z", 2)
        assert capture.token_count == 3

    def test_context_manager_auto_finishes(self):
        capture = TraceCapture()
        with capture.run(model="cm", prompt="ctx-mgr test", provider="test") as cap:
            cap.record_token("auto", 0)
        trace = capture.trace
        assert trace is not None
        assert trace.completed_at != ""
        assert len(trace.events) >= 4

    def test_context_manager_handles_exception(self):
        capture = TraceCapture()
        try:
            with capture.run(model="err-model", prompt="will fail", provider="test"):
                raise ValueError("Simulated crash")
        except ValueError:
            pass
        trace = capture.trace
        assert trace is not None
        # Trace should be auto-finished even on exception
        assert trace.completed_at != ""

    def test_context_manager_records_error_event(self):
        capture = TraceCapture()
        try:
            with capture.run(model="err2", prompt="error test", provider="test"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        trace = capture.trace
        error_events = [e for e in trace.events if e.type == "error"]
        assert len(error_events) >= 1
        assert "boom" in error_events[0].detail

    def test_record_error_manual(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        capture.record_error("Something went wrong")
        trace = capture.finish("partial response", None)
        error_events = [e for e in trace.events if e.type == "error"]
        assert len(error_events) == 1
        assert "Something went wrong" in error_events[0].detail


# ── Trace Event Structure ─────────────────────────────────────


class TestTraceEvents:
    def test_system_event_always_first(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        trace = capture.finish("r", None)
        assert trace.events[0].type == "system"

    def test_prompt_event_second(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        trace = capture.finish("r", None)
        assert trace.events[1].type == "prompt"

    def test_reasoning_event_present(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        trace = capture.finish("r", None)
        reasoning = [e for e in trace.events if e.type == "reasoning"]
        assert len(reasoning) == 1

    def test_response_event_last(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        trace = capture.finish("r", None)
        assert trace.events[-1].type == "response"

    def test_event_ids_are_unique(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        trace = capture.finish("r", None)
        ids = [e.id for e in trace.events]
        assert len(ids) == len(set(ids))

    def test_event_ids_contain_trace_prefix(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        trace = capture.finish("r", None)
        for event in trace.events:
            assert event.id.startswith(trace.trace_id)


# ── Metrics ───────────────────────────────────────────────────


class TestTraceMetrics:
    def test_ttft_is_set(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        capture.record_token("t", 0)
        trace = capture.finish("t", None)
        assert trace.metrics.ttft_ms >= 0

    def test_total_latency_is_positive(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        capture.record_token("t", 0)
        trace = capture.finish("t", None)
        assert trace.metrics.total_latency_ms > 0

    def test_token_timings_recorded(self, capture):
        capture.start(model="m", prompt="p", provider="test")
        capture.record_token("a", 0)
        capture.record_token("b", 1)
        capture.record_token("c", 2)
        trace = capture.finish("abc", None)
        assert len(trace.metrics.token_timings_ms) == 3

    def test_tokens_per_second_calculated_from_trace_data(self, capture):
        """When no metrics object is passed, tps is derived from token count and timing."""
        capture.start(model="m", prompt="p", provider="test")
        for i in range(10):
            capture.record_token("x", i)
        trace = capture.finish("xxxxxxxxxx", None)
        # Should calculate tps from token_count / generation_time
        assert trace.metrics.tokens_per_second >= 0
        assert trace.metrics.total_tokens == 10

    def test_metrics_override_when_provided(self, capture):
        """When an APICallMetrics object is passed, those values take precedence."""
        capture.start(model="m", prompt="p", provider="test")

        class MockMetrics:
            tokens_per_second = 150.0
            total_tokens = 500
            prompt_tokens = 100
            completion_tokens = 400

        trace = capture.finish("response", MockMetrics())
        assert trace.metrics.tokens_per_second == 150.0
        assert trace.metrics.total_tokens == 500


# ── TraceMetrics Dataclass ────────────────────────────────────


class TestTraceMetricsDataclass:
    def test_defaults(self):
        tm = TraceMetrics()
        assert tm.ttft_ms == 0.0
        assert tm.tokens_per_second == 0.0
        assert tm.token_timings_ms == []

    def test_full_population(self):
        tm = TraceMetrics(
            ttft_ms=42.0,
            tokens_per_second=88.5,
            total_tokens=256,
            prompt_tokens=56,
            completion_tokens=200,
            total_latency_ms=3200.0,
            memory_pressure_mb=1420.0,
            token_timings_ms=[1.2, 3.4, 5.6],
        )
        assert tm.ttft_ms == 42.0
        assert len(tm.token_timings_ms) == 3


# ── TraceArtifacts Dataclass ──────────────────────────────────


class TestTraceArtifactsDataclass:
    def test_defaults(self):
        ta = TraceArtifacts()
        assert ta.response == ""
        assert ta.logs == []
        assert ta.errors == []

    def test_with_data(self):
        ta = TraceArtifacts(
            response="Hello, world!",
            logs=["log1", "log2"],
            errors=["error1"],
        )
        assert ta.response == "Hello, world!"
        assert len(ta.errors) == 1


# ── wrap_stream Helper ────────────────────────────────────────


class TestWrapStream:
    def test_wrap_stream_records_tokens(self, capture):
        """Simulate a streaming response and verify tokens are recorded."""

        class FakeStream:
            """Minimal mock of an OpenAI streaming response."""

            def __init__(self, chunks):
                self._chunks = chunks
                self._idx = 0

            def __iter__(self):
                return self

            def __next__(self):
                if self._idx >= len(self._chunks):
                    raise StopIteration
                chunk = self._chunks[self._idx]
                self._idx += 1
                return chunk

        class FakeChunk:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]

        class FakeChoice:
            def __init__(self, content):
                self.delta = FakeDelta(content)

        class FakeDelta:
            def __init__(self, content):
                self.content = content

        capture.start(model="wrap-test", prompt="wrap", provider="test")
        fake_stream = FakeStream(
            [
                FakeChunk("Hello"),
                FakeChunk(" "),
                FakeChunk("world"),
            ]
        )

        collected = []
        for chunk in wrap_stream(fake_stream, capture):
            collected.append(chunk.choices[0].delta.content)

        assert collected == ["Hello", " ", "world"]
        assert capture.token_count == 3


# ── Provider Integration ──────────────────────────────────────


class TestProviderIntegration:
    def test_run_result_accepts_trace_id(self):
        """RunResult can carry a trace_id for linking to captured traces."""
        from providers.base import RunResult

        result = RunResult(
            response="test",
            model="m",
            provider="p",
            ttft_ms=100.0,
            total_time_ms=500.0,
            tokens_per_second=50.0,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            trace_id="trace-abc123",
        )
        assert result.trace_id == "trace-abc123"

    def test_run_result_trace_id_none_by_default(self):
        from providers.base import RunResult

        result = RunResult(
            response="test",
            model="m",
            provider="p",
            ttft_ms=100.0,
            total_time_ms=500.0,
            tokens_per_second=50.0,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        assert result.trace_id is None

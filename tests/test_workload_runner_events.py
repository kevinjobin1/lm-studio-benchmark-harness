"""
Unit tests for WorkloadRunner EventBus integration.

Mocks the OpenAI client to verify that EventBus events are emitted
with correct types and fields during workload evaluation.

Covers:
  - Non-streaming path (default): CompletionEvent, MetricEvent, RunLifecycleEvent
  - Streaming path: TokenGeneratedEvent per token + CompletionEvent
  - Error path (both streaming and non-streaming): ErrorEvent, CompletionEvent(success=False),
    RunLifecycleEvent(failed)
  - Batch lifecycle: RunLifecycleEvent at batch start/completion, aggregate MetricEvents
  - Event field correctness (model, provider, source, run_id, score components)
  - Empty batch edge case
"""

import unittest
from unittest.mock import MagicMock, patch
from typing import List

from events import (
    EventBus,
    TokenGeneratedEvent,
    CompletionEvent,
    RunLifecycleEvent,
    MetricEvent,
    ErrorEvent,
)

from core.workload import (
    WorkloadRunner,
    WorkloadTask,
    TaskType,
    TaskDifficulty,
)


# ═════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════

def make_sample_task(**overrides) -> WorkloadTask:
    """Create a minimal WorkloadTask for testing."""
    return WorkloadTask(
        task_id=overrides.get("task_id", "wl-test-001"),
        project_name=overrides.get("project_name", "test-project"),
        task_type=overrides.get("task_type", TaskType.IMPLEMENT_FEATURE),
        difficulty=overrides.get("difficulty", TaskDifficulty.MEDIUM),
        title=overrides.get("title", "Test task"),
        description=overrides.get("description", "A test task"),
        prompt=overrides.get("prompt", "Write a function that adds two numbers."),
        target_file=overrides.get("target_file", "src/test.ts"),
        language=overrides.get("language", "typescript"),
        framework=overrides.get("framework", "nestjs"),
        context_files=overrides.get("context_files", {"src/test.ts": "// existing code"}),
    )


def make_mock_chunk(content: str, finish_reason=None):
    """Create a mock streaming chunk with the given content."""
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = None
    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason
    choice.index = 0
    chunk.choices = [choice]
    chunk.object = "chat.completion.chunk"
    return chunk


def make_mock_stream(tokens: List[str]):
    """Create a mock streaming response that yields chunks."""
    chunks = []
    for i, token in enumerate(tokens):
        finish = "stop" if i == len(tokens) - 1 else None
        chunks.append(make_mock_chunk(token, finish))
    return chunks


def make_mock_response(text: str, completion_tokens: int = 10):
    """Create a mock non-streaming response."""
    response = MagicMock()
    choice = MagicMock()
    message = MagicMock()
    message.content = text
    message.tool_calls = None
    message.role = "assistant"
    choice.message = message
    choice.finish_reason = "stop"
    choice.index = 0
    response.choices = [choice]
    usage = MagicMock()
    usage.completion_tokens = completion_tokens
    usage.prompt_tokens = 15
    usage.total_tokens = 15 + completion_tokens
    response.usage = usage
    response.object = "chat.completion"
    return response


# ═════════════════════════════════════════════════════════════════════
#  NON-STREAMING PATH TESTS
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadRunnerNonStreaming(unittest.TestCase):
    """Tests for the non-streaming (default) path."""

    def setUp(self):
        self.bus = EventBus()
        self.events = []
        self.bus.subscribe_all(lambda e: self.events.append(e))

        self.task = make_sample_task()

        # Create runner with event bus
        self.runner = WorkloadRunner(
            api_base="http://localhost:9999/v1",
            api_key="test-key",
            model="test-model",
            event_bus=self.bus,
            stream=False,
        )

    @patch("openai.OpenAI")
    def test_completion_event_on_success(self, mock_openai):
        """Non-streaming success should emit CompletionEvent with correct fields."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nexport function add(a: number, b: number): number {\n  return a + b;\n}\n```",
            completion_tokens=15,
        )

        self.runner.run_task(self.task)

        completion_events = [e for e in self.events if isinstance(e, CompletionEvent)]
        self.assertEqual(len(completion_events), 1)
        ce = completion_events[0]
        self.assertTrue(ce.success)
        self.assertEqual(ce.model, "test-model")
        self.assertIn("export function add", ce.response)
        self.assertGreater(ce.tokens_used, 0)
        self.assertGreater(ce.latency_ms, 0)
        self.assertGreater(ce.ttft_ms, 0)
        self.assertGreater(ce.tokens_per_second, 0)
        self.assertEqual(ce.provider, "http://localhost:9999/v1")
        self.assertIn("workload", ce.source)
        self.assertIn("test-project", ce.run_id)

    @patch("openai.OpenAI")
    def test_metric_events_on_success(self, mock_openai):
        """Non-streaming success should emit MetricEvent for score and components."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nexport function add(a: number, b: number): number {\n  return a + b;\n}\n```",
        )

        self.runner.run_task(self.task)

        metric_events = [e for e in self.events if isinstance(e, MetricEvent)]
        # Should have overall score + 5 components = 6 metric events per task
        self.assertGreaterEqual(len(metric_events), 6,
                                f"Expected at least 6 MetricEvents, got {len(metric_events)}")

        # Check overall score metric
        score_metrics = [e for e in metric_events if e.name == "workload.score"]
        self.assertEqual(len(score_metrics), 1)
        self.assertGreater(score_metrics[0].value, 0)
        self.assertIn("task_id", score_metrics[0].tags)

        # Check component metrics
        component_names = {e.name for e in metric_events if e.name.startswith("workload.score.")}
        expected_components = {"workload.score.correctness", "workload.score.completeness",
                              "workload.score.code_quality", "workload.score.style_match",
                              "workload.score.efficiency"}
        self.assertSetEqual(component_names, expected_components,
                            f"Missing score components, got: {component_names}")

    @patch("openai.OpenAI")
    def test_lifecycle_events_on_success(self, mock_openai):
        """Non-streaming success should emit started + completed lifecycle events."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nexport function add(a: number, b: number): number {\n  return a + b;\n}\n```",
        )

        self.runner.run_task(self.task)

        lifecycle_events = [e for e in self.events if isinstance(e, RunLifecycleEvent)]
        self.assertEqual(len(lifecycle_events), 2,
                         f"Expected 2 lifecycle events (started + completed), got {len(lifecycle_events)}")

        started = lifecycle_events[0]
        completed = lifecycle_events[1]
        self.assertEqual(started.status, "started")
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.model, "test-model")
        self.assertEqual(completed.workload, "test-project")
        self.assertGreater(completed.duration_ms, 0)

    @patch("openai.OpenAI")
    def test_all_event_types_emitted_for_single_task(self, mock_openai):
        """A single successful task should emit RunLifecycle, Completion, and Metric events."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nexport function add(a: number, b: number): number {\n  return a + b;\n}\n```",
        )

        self.runner.run_task(self.task)

        event_types = {type(e).__name__ for e in self.events}
        expected_types = {"RunLifecycleEvent", "CompletionEvent", "MetricEvent"}
        self.assertSetEqual(event_types, expected_types,
                            f"Expected {expected_types}, got {event_types}")

    @patch("openai.OpenAI")
    def test_result_fields_match_events(self, mock_openai):
        """WorkloadResult fields should be consistent with emitted events."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nexport const x = 42;\n```",
            completion_tokens=8,
        )

        result = self.runner.run_task(self.task)

        completion = [e for e in self.events if isinstance(e, CompletionEvent)][0]
        self.assertEqual(completion.tokens_used, result.tokens_used)
        self.assertEqual(completion.model, result.model)
        self.assertEqual(completion.response, result.response)


# ═════════════════════════════════════════════════════════════════════
#  STREAMING PATH TESTS
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadRunnerStreaming(unittest.TestCase):
    """Tests for the streaming path (stream=True)."""

    def setUp(self):
        self.bus = EventBus()
        self.events = []
        self.bus.subscribe_all(lambda e: self.events.append(e))

        self.task = make_sample_task()

        self.runner = WorkloadRunner(
            api_base="http://localhost:9999/v1",
            api_key="test-key",
            model="test-model",
            event_bus=self.bus,
            stream=True,
        )

    @patch("openai.OpenAI")
    def test_token_generated_events_per_chunk(self, mock_openai):
        """Streaming should emit one TokenGeneratedEvent per chunk."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        tokens = ["Hello", " ", "world", "!"]
        mock_client.chat.completions.create.return_value = make_mock_stream(tokens)

        self.runner.run_task(self.task)

        token_events = [e for e in self.events if isinstance(e, TokenGeneratedEvent)]
        self.assertEqual(len(token_events), len(tokens))
        for i, te in enumerate(token_events):
            self.assertEqual(te.token, tokens[i])
            self.assertEqual(te.index, i)
            self.assertEqual(te.model, "test-model")

    @patch("openai.OpenAI")
    def test_token_events_have_correct_model_and_source(self, mock_openai):
        """TokenGeneratedEvent should have correct model, provider, source, run_id."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_stream(["hello"])

        self.runner.run_task(self.task)

        token_event = [e for e in self.events if isinstance(e, TokenGeneratedEvent)][0]
        self.assertEqual(token_event.model, "test-model")
        self.assertEqual(token_event.provider, "http://localhost:9999/v1")
        self.assertIn("workload", token_event.source)
        self.assertIn("test-project", token_event.run_id)
        self.assertGreater(token_event.timing_ms, 0)

    @patch("openai.OpenAI")
    def test_streaming_emits_all_event_types(self, mock_openai):
        """Streaming should emit TokenGenerated, Completion, Metric, and RunLifecycle events."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_stream(["hello", " ", "world"])

        self.runner.run_task(self.task)

        event_types = {type(e).__name__ for e in self.events}
        expected_types = {"TokenGeneratedEvent", "CompletionEvent", "MetricEvent", "RunLifecycleEvent"}
        self.assertSetEqual(event_types, expected_types,
                            f"Expected {expected_types}, got {event_types}")

    @patch("openai.OpenAI")
    def test_token_count_matches_tokens_used(self, mock_openai):
        """TokenGeneratedEvent count should match CompletionEvent tokens_used."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        tokens = ["hello", " ", "world", "!", "\n", "code"]
        mock_client.chat.completions.create.return_value = make_mock_stream(tokens)

        self.runner.run_task(self.task)

        token_count = len([e for e in self.events if isinstance(e, TokenGeneratedEvent)])
        completion = [e for e in self.events if isinstance(e, CompletionEvent)][0]

        self.assertEqual(completion.tokens_used, token_count,
                         f"CompletionEvent tokens_used ({completion.tokens_used}) should match "
                         f"TokenGeneratedEvent count ({token_count})")

    @patch("openai.OpenAI")
    def test_streaming_score_metrics(self, mock_openai):
        """Streaming path should still emit MetricEvent for scores."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_stream(["final", "code"])

        self.runner.run_task(self.task)

        score_metrics = [e for e in self.events if isinstance(e, MetricEvent) and e.name == "workload.score"]
        self.assertEqual(len(score_metrics), 1)
        self.assertGreater(score_metrics[0].value, 0)


# ═════════════════════════════════════════════════════════════════════
#  ERROR PATH TESTS (NON-STREAMING)
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadRunnerErrorPath(unittest.TestCase):
    """Tests for error handling in WorkloadRunner (non-streaming)."""

    def setUp(self):
        self.bus = EventBus()
        self.events = []
        self.bus.subscribe_all(lambda e: self.events.append(e))

        self.task = make_sample_task()

        self.runner = WorkloadRunner(
            api_base="http://localhost:9999/v1",
            api_key="test-key",
            model="test-model",
            event_bus=self.bus,
        )

    @patch("openai.OpenAI")
    def test_error_event_on_exception(self, mock_openai):
        """Exception should emit ErrorEvent with error details."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = ConnectionError("Connection refused")

        self.runner.run_task(self.task)

        error_events = [e for e in self.events if isinstance(e, ErrorEvent)]
        self.assertEqual(len(error_events), 1)
        ee = error_events[0]
        self.assertIn("Connection refused", ee.message)
        self.assertEqual(ee.exception, "ConnectionError")
        self.assertEqual(ee.component, "workload_runner")
        self.assertEqual(ee.severity, "error")

    @patch("openai.OpenAI")
    def test_completion_event_failed_on_exception(self, mock_openai):
        """Exception should emit CompletionEvent with success=False."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = TimeoutError("Request timed out")

        self.runner.run_task(self.task)

        completion_events = [e for e in self.events if isinstance(e, CompletionEvent)]
        self.assertEqual(len(completion_events), 1)
        ce = completion_events[0]
        self.assertFalse(ce.success)
        self.assertEqual(ce.error, "Request timed out")
        self.assertEqual(ce.tokens_used, 0)
        self.assertEqual(ce.ttft_ms, 0)
        self.assertEqual(ce.tokens_per_second, 0)

    @patch("openai.OpenAI")
    def test_lifecycle_failed_on_exception(self, mock_openai):
        """Exception should emit RunLifecycleEvent with status=failed."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("Unexpected error")

        self.runner.run_task(self.task)

        lifecycle_events = [e for e in self.events if isinstance(e, RunLifecycleEvent)]
        # Started + failed = 2 events
        self.assertEqual(len(lifecycle_events), 2)
        started = lifecycle_events[0]
        failed = lifecycle_events[1]
        self.assertEqual(started.status, "started")
        self.assertEqual(failed.status, "failed")
        self.assertIn("Unexpected error", (failed.error or ""))

    @patch("openai.OpenAI")
    def test_all_error_events_emitted(self, mock_openai):
        """Exception should emit ErrorEvent, CompletionEvent(failed), and RunLifecycleEvent(failed)."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = ValueError("Bad request")

        self.runner.run_task(self.task)

        event_types = {type(e).__name__ for e in self.events}
        expected_types = {"ErrorEvent", "CompletionEvent", "RunLifecycleEvent"}
        self.assertSetEqual(event_types, expected_types,
                            f"Error path should emit {expected_types}, got {event_types}")

    @patch("openai.OpenAI")
    def test_error_result_returned(self, mock_openai):
        """Exception should return a WorkloadResult with score=0 and error in failures."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Something broke")

        result = self.runner.run_task(self.task)

        self.assertEqual(result.score, 0.0)
        self.assertIn("Something broke", result.failures[0])
        self.assertEqual(result.response, "")
        self.assertEqual(result.response_time_ms, 0)


# ═════════════════════════════════════════════════════════════════════
#  ERROR PATH TESTS (STREAMING)
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadRunnerStreamingErrorPath(unittest.TestCase):
    """Tests for error handling in streaming mode."""

    def setUp(self):
        self.bus = EventBus()
        self.events = []
        self.bus.subscribe_all(lambda e: self.events.append(e))

        self.task = make_sample_task()

        self.runner = WorkloadRunner(
            api_base="http://localhost:9999/v1",
            api_key="test-key",
            model="test-model",
            event_bus=self.bus,
            stream=True,
        )

    @patch("openai.OpenAI")
    def test_streaming_error_emits_error_event(self, mock_openai):
        """Streaming error should emit ErrorEvent with correct details."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = ConnectionError("Stream failed")

        self.runner.run_task(self.task)

        error_events = [e for e in self.events if isinstance(e, ErrorEvent)]
        self.assertEqual(len(error_events), 1)
        ee = error_events[0]
        self.assertIn("Stream failed", ee.message)
        self.assertEqual(ee.exception, "ConnectionError")

    @patch("openai.OpenAI")
    def test_streaming_error_emits_failed_completion(self, mock_openai):
        """Streaming error should emit CompletionEvent with success=False."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = TimeoutError("Stream timed out")

        self.runner.run_task(self.task)

        completion = [e for e in self.events if isinstance(e, CompletionEvent)][0]
        self.assertFalse(completion.success)
        self.assertEqual(completion.error, "Stream timed out")

    @patch("openai.OpenAI")
    def test_streaming_error_emits_failed_lifecycle(self, mock_openai):
        """Streaming error should emit RunLifecycleEvent with status=failed."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = ValueError("Bad request")

        self.runner.run_task(self.task)

        lifecycle_events = [e for e in self.events if isinstance(e, RunLifecycleEvent)]
        self.assertEqual(len(lifecycle_events), 2)
        self.assertEqual(lifecycle_events[1].status, "failed")
        self.assertIn("Bad request", (lifecycle_events[1].error or ""))

    @patch("openai.OpenAI")
    def test_streaming_error_emits_no_token_events(self, mock_openai):
        """Streaming error should NOT emit any TokenGeneratedEvent."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("Crash")

        self.runner.run_task(self.task)

        token_events = [e for e in self.events if isinstance(e, TokenGeneratedEvent)]
        self.assertEqual(len(token_events), 0,
                         "No TokenGeneratedEvents should be emitted on error")

    @patch("openai.OpenAI")
    def test_streaming_error_returns_failed_result(self, mock_openai):
        """Streaming error should return a WorkloadResult with score=0."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Stream error")

        result = self.runner.run_task(self.task)

        self.assertEqual(result.score, 0.0)
        self.assertIn("Stream error", result.failures[0])


# ═════════════════════════════════════════════════════════════════════
#  BATCH PATH TESTS
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadRunnerBatch(unittest.TestCase):
    """Tests for batch lifecycle and aggregate metrics."""

    def setUp(self):
        self.bus = EventBus()
        self.events = []
        self.bus.subscribe_all(lambda e: self.events.append(e))

        self.tasks = [
            make_sample_task(task_id="wl-batch-001", title="Task 1"),
            make_sample_task(task_id="wl-batch-002", title="Task 2"),
        ]

        self.runner = WorkloadRunner(
            api_base="http://localhost:9999/v1",
            api_key="test-key",
            model="batch-model",
            event_bus=self.bus,
        )

    @patch("openai.OpenAI")
    def test_batch_lifecycle_events(self, mock_openai):
        """Batch should emit RunLifecycleEvent at start and completion."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nexport const x = 1;\n```",
        )

        self.runner.run_batch(self.tasks, verbose=False)

        # Filter by batch-level lifecycle events (contain '_batch_' in run_id)
        all_lifecycle = [e for e in self.events if isinstance(e, RunLifecycleEvent)]
        batch_lifecycles = [e for e in all_lifecycle if "_batch_" in (e.run_id or "")]
        self.assertGreaterEqual(len(batch_lifecycles), 2,
                                f"Expected at least 2 batch lifecycle events, "
                                f"got {len(batch_lifecycles)}")

        batch_started = [e for e in batch_lifecycles if e.status == "started"]
        batch_completed = [e for e in batch_lifecycles if e.status == "completed"]
        self.assertEqual(len(batch_started), 1)
        self.assertEqual(len(batch_completed), 1)

    @patch("openai.OpenAI")
    def test_batch_aggregate_metrics(self, mock_openai):
        """Batch should emit aggregate MetricEvents."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nconst x = 1;\n```",
        )

        self.runner.run_batch(self.tasks, verbose=False)

        batch_metrics = [e for e in self.events if isinstance(e, MetricEvent)
                         and e.name.startswith("workload.batch.")]
        metric_names = {e.name for e in batch_metrics}
        expected_metrics = {"workload.batch.avg_score", "workload.batch.avg_latency_ms",
                            "workload.batch.total_tokens"}
        self.assertSetEqual(metric_names, expected_metrics,
                            f"Expected batch metrics {expected_metrics}, got {metric_names}")

        # Verify values are sensible
        avg_score = [e for e in batch_metrics if e.name == "workload.batch.avg_score"][0]
        self.assertGreater(avg_score.value, 0)

        total_tokens = [e for e in batch_metrics if e.name == "workload.batch.total_tokens"][0]
        self.assertGreater(total_tokens.value, 0)

    @patch("openai.OpenAI")
    def test_batch_empty_returns_empty(self, mock_openai):
        """Empty batch should return empty list and emit no events."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        results = self.runner.run_batch([], verbose=False)

        self.assertEqual(len(results), 0)
        # No events should be emitted for an empty batch
        self.assertEqual(len(self.events), 0)

    @patch("openai.OpenAI")
    def test_batch_returns_correct_count(self, mock_openai):
        """Batch should return same number of results as input tasks."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nconsole.log('hello');\n```",
        )

        results = self.runner.run_batch(self.tasks, verbose=False)

        self.assertEqual(len(results), len(self.tasks))
        for i, r in enumerate(results):
            self.assertEqual(r.task_id, self.tasks[i].task_id)
            self.assertGreater(r.score, 0)


# ═════════════════════════════════════════════════════════════════════
#  EVENT FIELD CORRECTNESS TESTS
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadRunnerEventFields(unittest.TestCase):
    """Tests for correctness of event field values."""

    def setUp(self):
        self.bus = EventBus()
        self.events = []
        self.bus.subscribe_all(lambda e: self.events.append(e))

        self.task = make_sample_task(
            task_id="wl-field-test",
            project_name="test-project",
            prompt="Write a simple function.",
        )

        self.runner = WorkloadRunner(
            api_base="http://custom-api:8080/v1",
            api_key="custom-key",
            model="custom-model-v2",
            event_bus=self.bus,
        )

    @patch("openai.OpenAI")
    def test_source_format(self, mock_openai):
        """Event source should follow 'workload.{project_name}' format."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nconst x = 1;\n```",
        )

        self.runner.run_task(self.task)

        for event in self.events:
            if hasattr(event, "source") and event.source:
                self.assertEqual(event.source, "workload.test-project",
                                 f"Unexpected source '{event.source}' in {type(event).__name__}")

    @patch("openai.OpenAI")
    def test_run_id_format(self, mock_openai):
        """Event run_id should start with 'workload_test-project_'."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nconst x = 1;\n```",
        )

        self.runner.run_task(self.task)

        for event in self.events:
            if hasattr(event, "run_id") and event.run_id:
                self.assertTrue(
                    event.run_id.startswith("workload_test-project_"),
                    f"Unexpected run_id '{event.run_id}' in {type(event).__name__}: "
                    f"expected to start with 'workload_test-project_'",
                )

    @patch("openai.OpenAI")
    def test_metric_tags_contain_task_id(self, mock_openai):
        """MetricEvent tags should include task_id, task_type, and project."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nfunction foo() { return 1; }\n```",
        )

        self.runner.run_task(self.task)

        score_metrics = [e for e in self.events if isinstance(e, MetricEvent)
                         and e.name == "workload.score"]
        self.assertEqual(len(score_metrics), 1)
        tags = score_metrics[0].tags
        self.assertEqual(tags.get("task_id"), "wl-field-test")
        self.assertEqual(tags.get("task_type"), "implement_feature")
        self.assertEqual(tags.get("project"), "test-project")

    @patch("openai.OpenAI")
    def test_model_name_in_all_events(self, mock_openai):
        """All event types should carry the model name."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nconst x = 1;\n```",
        )

        self.runner.run_task(self.task)

        for event in self.events:
            if hasattr(event, "model"):
                self.assertEqual(event.model, "custom-model-v2",
                                 f"Unexpected model '{event.model}' in {type(event).__name__}")

    @patch("openai.OpenAI")
    def test_completion_event_tokens_per_second(self, mock_openai):
        """CompletionEvent should have a reasonable tokens_per_second value."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "This is a test response with some content to verify metrics.",
            completion_tokens=14,
        )

        self.runner.run_task(self.task)

        completion = [e for e in self.events if isinstance(e, CompletionEvent)][0]
        self.assertGreater(completion.tokens_per_second, 0,
                           "tokens_per_second should be positive")
        self.assertGreater(completion.latency_ms, 0,
                           "latency_ms should be positive")
        self.assertIsNone(completion.error,
                          "successful completion should have no error")


class TestWorkloadRunnerEventOrdering(unittest.TestCase):
    """Tests for the order in which events are emitted."""

    def setUp(self):
        self.bus = EventBus()
        self.events = []
        self.bus.subscribe_all(lambda e: self.events.append(e))

        self.task = make_sample_task()

        self.runner = WorkloadRunner(
            api_base="http://localhost:9999/v1",
            api_key="test-key",
            model="test-model",
            event_bus=self.bus,
        )

    @patch("openai.OpenAI")
    def test_event_ordering_success(self, mock_openai):
        """Events should follow order: started → CompletionEvent → MetricEvent → completed."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response(
            "```typescript\nconst x = 1;\n```",
        )

        self.runner.run_task(self.task)

        type_sequence = [type(e).__name__ for e in self.events]

        # Find lifecycle indices
        lifecycle_indices = [i for i, n in enumerate(type_sequence) if n == "RunLifecycleEvent"]
        first_lifecycle_idx = lifecycle_indices[0]
        last_lifecycle_idx = lifecycle_indices[-1]

        # First lifecycle event should be started
        self.assertEqual(self.events[first_lifecycle_idx].status, "started",
                         "First lifecycle event should be 'started'")

        # Last lifecycle event should be completed
        self.assertEqual(self.events[last_lifecycle_idx].status, "completed",
                         "Last lifecycle event should be 'completed'")

        # CompletionEvent should be between the two lifecycle events
        completion_indices = [i for i, n in enumerate(type_sequence) if n == "CompletionEvent"]
        for ci in completion_indices:
            self.assertGreater(ci, first_lifecycle_idx,
                               "CompletionEvent should come after started")
            self.assertLess(ci, last_lifecycle_idx,
                            "CompletionEvent should come before completed")

    @patch("openai.OpenAI")
    def test_event_ordering_error(self, mock_openai):
        """Error should follow: started → ErrorEvent → CompletionEvent(failed) → failed."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("Fail")

        self.runner.run_task(self.task)

        type_sequence = [type(e).__name__ for e in self.events]

        # Find indices
        error_idx = next(i for i, n in enumerate(type_sequence) if n == "ErrorEvent")
        completion_idx = next(i for i, n in enumerate(type_sequence) if n == "CompletionEvent")
        lifecycle_indices = [i for i, n in enumerate(type_sequence) if n == "RunLifecycleEvent"]

        # Order should be: started → ErrorEvent → CompletionEvent(failed) → failed
        self.assertGreater(error_idx, lifecycle_indices[0],
                           "ErrorEvent should come after started")
        self.assertGreater(completion_idx, error_idx,
                           "CompletionEvent should come after ErrorEvent")
        self.assertGreater(lifecycle_indices[-1], completion_idx,
                           "Failed lifecycle should come after CompletionEvent")


# ═════════════════════════════════════════════════════════════════════
#  EDGE CASES
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadRunnerEdgeCases(unittest.TestCase):
    """Edge cases for WorkloadRunner EventBus integration."""

    def test_custom_event_bus(self):
        """WorkloadRunner should use the provided event bus instance."""
        bus = EventBus()
        runner = WorkloadRunner(event_bus=bus)
        self.assertIs(runner.event_bus, bus)

    def test_default_event_bus(self):
        """WorkloadRunner should use default_bus if no event_bus provided."""
        from events import default_bus
        runner = WorkloadRunner()
        self.assertIs(runner.event_bus, default_bus)

    def test_stream_defaults_to_false(self):
        """WorkloadRunner should default to non-streaming (backward compat)."""
        runner = WorkloadRunner()
        self.assertFalse(runner.stream)

    def test_scorer_uses_default_if_not_provided(self):
        """WorkloadRunner should create a default WorkloadScorer if none provided."""
        runner = WorkloadRunner()
        from core.workload import WorkloadScorer
        self.assertIsInstance(runner.scorer, WorkloadScorer)


if __name__ == "__main__":
    unittest.main()

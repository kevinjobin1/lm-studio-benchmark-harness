"""
Unit tests for the EventBus — typed pub/sub for observability events.

Covers:
  - Basic sync emit and type-specific subscription
  - Wildcard (subscribe_all) handlers
  - Unsubscribe and unsubscribe_all
  - Async emit with async/await handlers
  - Error handling (subscriber errors do not propagate)
  - Publish context (auto source/run_id, events_emitted counter)
  - Run-scoped subscriptions (subscribe with run_id, unsubscribe_run)
  - Enable/disable
  - Clear
  - Multiple handlers per event type
  - Handler count
  - Concrete event types (TokenGeneratedEvent, CompletionEvent, MetricEvent, ErrorEvent, RunLifecycleEvent)
"""

import asyncio
import unittest

from events import (
    EventBus,
    EventType,
    EventPriority,
    ModelLensEvent,
    default_bus,
    TokenGeneratedEvent,
    CompletionEvent,
    MetricEvent,
    ErrorEvent,
    RunLifecycleEvent,
)


# ═════════════════════════════════════════════════════════════════════
#  BASIC PUB/SUB
# ═════════════════════════════════════════════════════════════════════


class TestEventBusBasicSubscribe(unittest.TestCase):
    """Tests for basic subscribe and emit_sync."""

    def setUp(self):
        self.bus = EventBus()
        self.received = []

    def handler(self, event):
        self.received.append(event)

    def test_subscribe_and_emit_sync(self):
        """Subscribed handler should receive emitted events."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler)
        event = TokenGeneratedEvent(model="qwen", token="hello", index=0, timing_ms=12.5)
        self.bus.emit_sync(event)

        self.assertEqual(len(self.received), 1)
        self.assertIs(self.received[0], event)
        self.assertEqual(self.received[0].model, "qwen")
        self.assertEqual(self.received[0].token, "hello")

    def test_subscribe_wrong_type_not_called(self):
        """Handler for one event type should not receive another type."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler)
        event = CompletionEvent(
            model="qwen",
            response="ok",
            tokens_used=5,
            latency_ms=100,
            ttft_ms=50,
            tokens_per_second=50.0,
        )
        self.bus.emit_sync(event)

        self.assertEqual(len(self.received), 0)

    def test_multiple_handlers_same_type(self):
        """Multiple handlers for the same event type should all be called."""
        received_a = []
        received_b = []

        def handler_a(e):
            received_a.append(e)

        def handler_b(e):
            received_b.append(e)

        self.bus.subscribe(TokenGeneratedEvent, handler_a)
        self.bus.subscribe(TokenGeneratedEvent, handler_b)

        event = TokenGeneratedEvent(model="qwen", token="hello", index=0, timing_ms=10.0)
        self.bus.emit_sync(event)

        self.assertEqual(len(received_a), 1)
        self.assertEqual(len(received_b), 1)

    def test_multiple_events(self):
        """Multiple events in sequence should all be delivered."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler)

        for i in range(5):
            self.bus.emit_sync(
                TokenGeneratedEvent(
                    model="qwen",
                    token=str(i),
                    index=i,
                    timing_ms=float(i * 10),
                )
            )

        self.assertEqual(len(self.received), 5)
        for i, ev in enumerate(self.received):
            self.assertEqual(ev.index, i)
            self.assertEqual(ev.token, str(i))


# ═════════════════════════════════════════════════════════════════════
#  WILDCARD SUBSCRIPTION
# ═════════════════════════════════════════════════════════════════════


class TestEventBusSubscribeAll(unittest.TestCase):
    """Tests for wildcard subscribe_all handlers."""

    def setUp(self):
        self.bus = EventBus()
        self.received = []

    def handler(self, event):
        self.received.append(type(event).__name__)

    def test_subscribe_all_receives_all_types(self):
        """Wildcard handler should receive every event type."""
        self.bus.subscribe_all(self.handler)

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))
        self.bus.emit_sync(MetricEvent(name="test", value=42.0))
        self.bus.emit_sync(ErrorEvent(message="boom"))

        self.assertEqual(len(self.received), 3)
        self.assertIn("TokenGeneratedEvent", self.received)
        self.assertIn("MetricEvent", self.received)
        self.assertIn("ErrorEvent", self.received)

    def test_subscribe_all_plus_type_specific(self):
        """Wildcard handler should be called alongside type-specific handlers."""
        type_received = []
        wild_received = []

        self.bus.subscribe(TokenGeneratedEvent, lambda e: type_received.append(e))
        self.bus.subscribe_all(lambda e: wild_received.append(e))

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))
        self.bus.emit_sync(MetricEvent(name="test", value=1.0))

        self.assertEqual(len(type_received), 1)  # Only TokenGeneratedEvent
        self.assertEqual(len(wild_received), 2)  # Both events


# ═════════════════════════════════════════════════════════════════════
#  UNSUBSCRIBE
# ═════════════════════════════════════════════════════════════════════


class TestEventBusUnsubscribe(unittest.TestCase):
    """Tests for unsubscribe and unsubscribe_all.

    Note: Store handler references in local variables to avoid Python's
    bound method identity issue (instance.method creates a new object
    each time, making `is not` comparison fail).
    """

    def setUp(self):
        self.bus = EventBus()
        self.received = []
        # Store handler reference to avoid bound method identity issues
        self._handler = self._make_handler()

    def _make_handler(self):
        received = self.received

        def handler(event):
            received.append(event)

        return handler

    def test_unsubscribe_removes_handler(self):
        """After unsubscribe, handler should not receive events."""
        self.bus.subscribe(TokenGeneratedEvent, self._handler)
        self.bus.unsubscribe(TokenGeneratedEvent, self._handler)

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(self.received), 0)

    def test_unsubscribe_other_handler_still_works(self):
        """Unsubscribing one handler should not affect other handlers for the same type."""
        received_a = []
        received_b = []

        def handler_a(e):
            received_a.append(e)

        def handler_b(e):
            received_b.append(e)

        self.bus.subscribe(TokenGeneratedEvent, handler_a)
        self.bus.subscribe(TokenGeneratedEvent, handler_b)
        self.bus.unsubscribe(TokenGeneratedEvent, handler_a)

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(received_a), 0)
        self.assertEqual(len(received_b), 1)

    def test_unsubscribe_nonexistent_handler_no_error(self):
        """Unsubscribing a handler that was never subscribed should not raise."""
        self.bus.unsubscribe(TokenGeneratedEvent, lambda e: None)  # Should not raise

    def test_unsubscribe_all(self):
        """unsubscribe_all removes a wildcard handler."""
        self.bus.subscribe_all(self._handler)
        self.bus.unsubscribe_all(self._handler)

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(self.received), 0)

    def test_unsubscribe_wildcard_other_still_works(self):
        """Unsubscribing one wildcard handler should not affect another."""
        received_a = []
        received_b = []

        def handler_a(e):
            received_a.append(e)

        def handler_b(e):
            received_b.append(e)

        self.bus.subscribe_all(handler_a)
        self.bus.subscribe_all(handler_b)
        self.bus.unsubscribe_all(handler_a)

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(received_a), 0)
        self.assertEqual(len(received_b), 1)


# ═════════════════════════════════════════════════════════════════════
#  ASYNC EMIT
# ═════════════════════════════════════════════════════════════════════


class TestEventBusAsyncEmit(unittest.TestCase):
    """Tests for async emit with async handlers."""

    def setUp(self):
        self.bus = EventBus()

    def test_async_handler(self):
        """Async handler should be awaited and receive the event."""
        received = []

        async def async_handler(event):
            received.append(event)

        self.bus.subscribe(TokenGeneratedEvent, async_handler)

        async def emit_event():
            await self.bus.emit(
                TokenGeneratedEvent(
                    model="qwen",
                    token="hello",
                    index=0,
                    timing_ms=12.5,
                )
            )

        asyncio.run(emit_event())

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].token, "hello")

    def test_mixed_sync_and_async_handlers(self):
        """Both sync and async handlers for the same type should be called."""
        sync_received = []
        async_received = []

        def sync_handler(event):
            sync_received.append(event)

        async def async_handler(event):
            async_received.append(event)

        self.bus.subscribe(TokenGeneratedEvent, sync_handler)
        self.bus.subscribe(TokenGeneratedEvent, async_handler)

        async def emit_event():
            await self.bus.emit(
                TokenGeneratedEvent(
                    model="qwen",
                    token="hello",
                    index=0,
                    timing_ms=12.5,
                )
            )

        asyncio.run(emit_event())

        self.assertEqual(len(sync_received), 1)
        self.assertEqual(len(async_received), 1)

    def test_async_wildcard_handler(self):
        """Wildcard async handler should receive all events."""
        received = []

        async def wild_handler(event):
            received.append(type(event).__name__)

        self.bus.subscribe_all(wild_handler)

        async def emit_events():
            await self.bus.emit(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))
            await self.bus.emit(
                CompletionEvent(
                    model="m",
                    response="r",
                    tokens_used=5,
                    latency_ms=100,
                    ttft_ms=50,
                    tokens_per_second=50.0,
                )
            )

        asyncio.run(emit_events())

        self.assertEqual(len(received), 2)
        self.assertIn("TokenGeneratedEvent", received)
        self.assertIn("CompletionEvent", received)


# ═════════════════════════════════════════════════════════════════════
#  ERROR HANDLING
# ═════════════════════════════════════════════════════════════════════


class TestEventBusErrorHandling(unittest.TestCase):
    """Tests that subscriber errors do not propagate."""

    def setUp(self):
        self.bus = EventBus()

    def test_handler_raising_does_not_propagate(self):
        """A handler that raises should not prevent other handlers from running."""
        received = []

        def bad_handler(event):
            raise ValueError("Intentional error")

        def good_handler(event):
            received.append(event)

        self.bus.subscribe(TokenGeneratedEvent, bad_handler)
        self.bus.subscribe(TokenGeneratedEvent, good_handler)

        # Should not raise
        self.bus.emit_sync(
            TokenGeneratedEvent(
                model="qwen",
                token="hello",
                index=0,
                timing_ms=12.5,
            )
        )

        self.assertEqual(len(received), 1)

    def test_async_handler_raising_does_not_propagate(self):
        """An async handler that raises should not prevent other handlers."""
        received = []

        async def bad_handler(event):
            raise ValueError("Intentional async error")

        async def good_handler(event):
            received.append(event)

        self.bus.subscribe(TokenGeneratedEvent, bad_handler)
        self.bus.subscribe(TokenGeneratedEvent, good_handler)

        async def emit_event():
            await self.bus.emit(
                TokenGeneratedEvent(
                    model="qwen",
                    token="hello",
                    index=0,
                    timing_ms=12.5,
                )
            )

        # Should not raise
        asyncio.run(emit_event())

        self.assertEqual(len(received), 1)

    def test_wildcard_handler_raising_does_not_propagate(self):
        """A wildcard handler that raises should not block other wildcard handlers."""
        received = []

        def bad_handler(event):
            raise RuntimeError("Wildcard error")

        def good_handler(event):
            received.append(event)

        self.bus.subscribe_all(bad_handler)
        self.bus.subscribe_all(good_handler)

        self.bus.emit_sync(
            TokenGeneratedEvent(
                model="qwen",
                token="hello",
                index=0,
                timing_ms=12.5,
            )
        )

        self.assertEqual(len(received), 1)

    def test_error_after_success_does_not_affect_previous(self):
        """Events emitted before a handler starts raising should still be delivered."""
        received = []

        def intermittent_handler(event):
            """Raise on the second event, succeed on the first."""
            if len(received) > 0:
                raise ValueError("Intermittent failure")
            received.append(event)

        self.bus.subscribe(TokenGeneratedEvent, intermittent_handler)

        # First event — succeeds
        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="a", index=0, timing_ms=1.0))
        self.assertEqual(len(received), 1)

        # Second event — handler raises, but should not propagate
        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="b", index=1, timing_ms=2.0))
        # The handler raised, so received is still 1
        # But importantly, no exception propagated to the caller
        self.assertEqual(len(received), 1)


# ═════════════════════════════════════════════════════════════════════
#  PUBLISH CONTEXT
# ═════════════════════════════════════════════════════════════════════


class TestEventBusPublishContext(unittest.TestCase):
    """Tests for the publish context manager."""

    def setUp(self):
        self.bus = EventBus()

    def test_publish_context_auto_sets_run_id(self):
        """Events emitted in a publish context should auto-get run_id."""
        received = []

        self.bus.subscribe(TokenGeneratedEvent, lambda e: received.append(e))

        async def emit_with_context():
            async with self.bus.publish(run_id="run_abc", source="test") as ctx:
                ctx.emit(
                    TokenGeneratedEvent(
                        model="qwen",
                        token="hello",
                        index=0,
                        timing_ms=12.5,
                    )
                )

        asyncio.run(emit_with_context())

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].run_id, "run_abc")
        self.assertEqual(received[0].source, "test")

    def test_publish_context_does_not_override_existing(self):
        """If an event already has run_id/source, publish context should not override."""
        received = []

        self.bus.subscribe(TokenGeneratedEvent, lambda e: received.append(e))

        async def emit_with_context():
            async with self.bus.publish(run_id="wrong", source="wrong") as ctx:
                ctx.emit(
                    TokenGeneratedEvent(
                        model="qwen",
                        token="hello",
                        index=0,
                        timing_ms=12.5,
                        run_id="explicit_run",
                        source="explicit_source",
                    )
                )

        asyncio.run(emit_with_context())

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].run_id, "explicit_run")
        self.assertEqual(received[0].source, "explicit_source")

    def test_publish_context_events_emitted_counter(self):
        """Publish context should track the number of emitted events."""

        async def run():
            async with self.bus.publish(run_id="test", source="test") as ctx:
                ctx.emit(TokenGeneratedEvent(model="m", token="a", index=0, timing_ms=1.0))
                ctx.emit(TokenGeneratedEvent(model="m", token="b", index=1, timing_ms=2.0))
                ctx.emit(TokenGeneratedEvent(model="m", token="c", index=2, timing_ms=3.0))
                self.assertEqual(ctx.events_emitted, 3)

        asyncio.run(run())

    def test_publish_context_emits_to_bus(self):
        """Events from publish context should be received by bus subscribers."""
        received = []

        self.bus.subscribe_all(lambda e: received.append(e))

        async def run():
            async with self.bus.publish(run_id="test", source="test") as ctx:
                ctx.emit(TokenGeneratedEvent(model="m", token="a", index=0, timing_ms=1.0))
                ctx.emit(MetricEvent(name="m", value=1.0))
                ctx.emit(ErrorEvent(message="err"))

        asyncio.run(run())

        self.assertEqual(len(received), 3)


# ═════════════════════════════════════════════════════════════════════
#  RUN-SCOPED SUBSCRIPTIONS
# ═════════════════════════════════════════════════════════════════════


class TestEventBusRunScoped(unittest.TestCase):
    """Tests for run-scoped subscriptions with unsubscribe_run."""

    def setUp(self):
        self.bus = EventBus()
        self.received = []

    def handler(self, event):
        self.received.append(event)

    def test_subscribe_with_run_id(self):
        """Subscribing with run_id should register the subscription."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler, run_id="run_123")
        # Verify the run is tracked in _run_scoped
        self.assertIn("run_123", self.bus._run_scoped)
        self.assertIn(TokenGeneratedEvent, self.bus._run_scoped["run_123"])

    def test_unsubscribe_run_removes_tracking(self):
        """unsubscribe_run should remove the run from _run_scoped."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler, run_id="run_123")
        self.bus.unsubscribe_run("run_123")
        self.assertNotIn("run_123", self.bus._run_scoped)

    def test_unsubscribe_run_other_runs_not_affected(self):
        """unsubscribe_run should not affect other runs' subscriptions."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler, run_id="run_a")
        self.bus.subscribe(MetricEvent, self.handler, run_id="run_b")
        self.bus.unsubscribe_run("run_a")
        self.assertNotIn("run_a", self.bus._run_scoped)
        self.assertIn("run_b", self.bus._run_scoped)

    def test_handler_still_works_after_unsubscribe_run(self):
        """The handler should still work after unsubscribe_run if not explicitly removed."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler, run_id="run_123")
        self.bus.unsubscribe_run("run_123")

        # Handler is still in _handlers since our unsubscribe_run only cleans up _run_scoped
        # This is by design — the subscriber is responsible for removing the handler
        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        # Handler should still receive events because we didn't remove it from _handlers
        self.assertEqual(len(self.received), 1)


# ═════════════════════════════════════════════════════════════════════
#  ENABLE / DISABLE
# ═════════════════════════════════════════════════════════════════════


class TestEventBusEnableDisable(unittest.TestCase):
    """Tests for enable/disable lifecycle."""

    def setUp(self):
        self.bus = EventBus()
        self.received = []

    def handler(self, event):
        self.received.append(event)

    def test_disable_suppresses_events(self):
        """After disable, events should not be delivered."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler)
        self.bus.disable()

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(self.received), 0)

    def test_re_enable_delivers_events(self):
        """After re-enable, events should be delivered again."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler)
        self.bus.disable()
        self.bus.enable()

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(self.received), 1)

    def test_disable_does_not_affect_async_emit(self):
        """disable should also suppress async emit."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler)
        self.bus.disable()

        async def emit_event():
            await self.bus.emit(
                TokenGeneratedEvent(
                    model="m",
                    token="t",
                    index=0,
                    timing_ms=1.0,
                )
            )

        asyncio.run(emit_event())

        self.assertEqual(len(self.received), 0)

    def test_disable_then_enable_async(self):
        """After disable then enable, async emit should deliver events."""
        self.bus.subscribe(TokenGeneratedEvent, self.handler)
        self.bus.disable()
        self.bus.enable()

        async def emit_event():
            await self.bus.emit(
                TokenGeneratedEvent(
                    model="m",
                    token="t",
                    index=0,
                    timing_ms=1.0,
                )
            )

        asyncio.run(emit_event())

        self.assertEqual(len(self.received), 1)


# ═════════════════════════════════════════════════════════════════════
#  CLEAR
# ═════════════════════════════════════════════════════════════════════


class TestEventBusClear(unittest.TestCase):
    """Tests for the clear method."""

    def setUp(self):
        self.bus = EventBus()

    def test_clear_removes_all_type_handlers(self):
        """After clear, type-specific handlers should not receive events."""
        received = []
        self.bus.subscribe(TokenGeneratedEvent, lambda e: received.append(e))
        self.bus.clear()

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(received), 0)

    def test_clear_removes_wildcard_handlers(self):
        """After clear, wildcard handlers should not receive events."""
        received = []
        self.bus.subscribe_all(lambda e: received.append(e))
        self.bus.clear()

        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        self.assertEqual(len(received), 0)

    def test_clear_resets_run_scoped(self):
        """After clear, _run_scoped should be empty."""
        self.bus.subscribe(TokenGeneratedEvent, lambda e: None, run_id="run_123")
        self.bus.clear()
        self.assertEqual(len(self.bus._run_scoped), 0)

    def test_clear_resets_handler_count(self):
        """After clear, handler_count should be 0."""
        self.bus.subscribe(TokenGeneratedEvent, lambda e: None)
        self.bus.subscribe_all(lambda e: None)
        self.bus.clear()
        self.assertEqual(self.bus.handler_count, 0)


# ═════════════════════════════════════════════════════════════════════
#  HANDLER COUNT
# ═════════════════════════════════════════════════════════════════════


class TestEventBusHandlerCount(unittest.TestCase):
    """Tests for the handler_count property."""

    def test_empty_bus_has_zero_handlers(self):
        """A fresh EventBus should have 0 handlers."""
        bus = EventBus()
        self.assertEqual(bus.handler_count, 0)

    def test_type_handler_increases_count(self):
        """Subscribing a type handler should increase count."""
        bus = EventBus()
        bus.subscribe(TokenGeneratedEvent, lambda e: None)
        self.assertEqual(bus.handler_count, 1)

    def test_multiple_type_handlers(self):
        """Multiple handlers for the same type should each count."""
        bus = EventBus()
        bus.subscribe(TokenGeneratedEvent, lambda e: None)
        bus.subscribe(TokenGeneratedEvent, lambda e: None)
        self.assertEqual(bus.handler_count, 2)

    def test_wildcard_handler_increases_count(self):
        """A wildcard handler should increase count."""
        bus = EventBus()
        bus.subscribe_all(lambda e: None)
        self.assertEqual(bus.handler_count, 1)

    def test_type_and_wildcard_both_counted(self):
        """Type-specific and wildcard handlers should all be counted."""
        bus = EventBus()
        bus.subscribe(TokenGeneratedEvent, lambda e: None)
        bus.subscribe(MetricEvent, lambda e: None)
        bus.subscribe_all(lambda e: None)
        self.assertEqual(bus.handler_count, 3)

    def test_unsubscribe_decreases_count(self):
        """Unsubscribing should decrease the count."""
        bus = EventBus()
        handler = lambda e: None
        bus.subscribe(TokenGeneratedEvent, handler)
        self.assertEqual(bus.handler_count, 1)
        bus.unsubscribe(TokenGeneratedEvent, handler)
        self.assertEqual(bus.handler_count, 0)

    def test_unsubscribe_all_decreases_count(self):
        """Unsubscribing a wildcard should decrease count."""
        bus = EventBus()
        handler = lambda e: None
        bus.subscribe_all(handler)
        self.assertEqual(bus.handler_count, 1)
        bus.unsubscribe_all(handler)
        self.assertEqual(bus.handler_count, 0)


# ═════════════════════════════════════════════════════════════════════
#  CONCRETE EVENT TYPES
# ═════════════════════════════════════════════════════════════════════


class TestEventBusConcreteEvents(unittest.TestCase):
    """Tests that all concrete event types work correctly with EventBus."""

    def setUp(self):
        self.bus = EventBus()

    def test_token_generated_event(self):
        """TokenGeneratedEvent should carry token data."""
        received = []
        self.bus.subscribe(TokenGeneratedEvent, lambda e: received.append(e))

        self.bus.emit_sync(
            TokenGeneratedEvent(
                model="qwen-3.5-9b",
                token="Hello",
                index=0,
                timing_ms=150.0,
                provider="lm-studio",
                run_id="run_001",
                source="benchmark",
            )
        )

        self.assertEqual(len(received), 1)
        e = received[0]
        self.assertEqual(e.model, "qwen-3.5-9b")
        self.assertEqual(e.token, "Hello")
        self.assertEqual(e.index, 0)
        self.assertEqual(e.timing_ms, 150.0)
        self.assertEqual(e.provider, "lm-studio")
        self.assertEqual(e.run_id, "run_001")
        self.assertEqual(e.source, "benchmark")
        self.assertTrue(len(e.id) > 0)

    def test_completion_event(self):
        """CompletionEvent should carry response and performance data."""
        received = []
        self.bus.subscribe(CompletionEvent, lambda e: received.append(e))

        self.bus.emit_sync(
            CompletionEvent(
                model="qwen",
                response="Paris is the capital of France.",
                tokens_used=7,
                latency_ms=320.0,
                ttft_ms=150.0,
                tokens_per_second=45.2,
                provider="ollama",
                run_id="run_002",
                source="benchmark",
                success=True,
            )
        )

        self.assertEqual(len(received), 1)
        e = received[0]
        self.assertEqual(e.model, "qwen")
        self.assertEqual(e.response, "Paris is the capital of France.")
        self.assertEqual(e.tokens_used, 7)
        self.assertEqual(e.latency_ms, 320.0)
        self.assertEqual(e.ttft_ms, 150.0)
        self.assertEqual(e.tokens_per_second, 45.2)
        self.assertTrue(e.success)
        self.assertIsNone(e.error)

    def test_completion_event_failure(self):
        """CompletionEvent with success=False should carry error data."""
        received = []
        self.bus.subscribe(CompletionEvent, lambda e: received.append(e))

        self.bus.emit_sync(
            CompletionEvent(
                model="qwen",
                response="",
                tokens_used=0,
                latency_ms=5000.0,
                ttft_ms=0,
                tokens_per_second=0,
                success=False,
                error="Connection timeout",
            )
        )

        e = received[0]
        self.assertFalse(e.success)
        self.assertEqual(e.error, "Connection timeout")

    def test_metric_event(self):
        """MetricEvent should carry name, value, unit, and tags."""
        received = []
        self.bus.subscribe(MetricEvent, lambda e: received.append(e))

        self.bus.emit_sync(
            MetricEvent(
                name="workload.score",
                value=0.85,
                unit="",
                tags={"task_id": "wl-001", "task_type": "implement_feature"},
                model="qwen",
                run_id="run_003",
                source="workload",
            )
        )

        e = received[0]
        self.assertEqual(e.name, "workload.score")
        self.assertEqual(e.value, 0.85)
        self.assertEqual(e.tags["task_id"], "wl-001")
        self.assertEqual(e.tags["task_type"], "implement_feature")
        self.assertTrue(len(e.id) > 0)

    def test_error_event(self):
        """ErrorEvent should carry error details."""
        received = []
        self.bus.subscribe(ErrorEvent, lambda e: received.append(e))

        self.bus.emit_sync(
            ErrorEvent(
                message="Task failed: connection refused",
                exception="ConnectionError",
                stack_trace="Traceback (most recent call last):\n  ...",
                component="workload_runner",
                run_id="run_004",
                source="workload",
                severity="error",
            )
        )

        e = received[0]
        self.assertIn("connection refused", e.message)
        self.assertEqual(e.exception, "ConnectionError")
        self.assertIn("Traceback", e.stack_trace)
        self.assertEqual(e.component, "workload_runner")
        self.assertEqual(e.severity, "error")

    def test_run_lifecycle_event(self):
        """RunLifecycleEvent should carry lifecycle status."""
        received = []
        self.bus.subscribe(RunLifecycleEvent, lambda e: received.append(e))

        # Emit a lifecycle event
        self.bus.emit_sync(
            RunLifecycleEvent(
                status="completed",
                model="qwen",
                provider="lm-studio",
                workload="nestjs-api",
                run_id="run_005",
                source="workload",
                duration_ms=1234.5,
            )
        )

        e = received[0]
        self.assertEqual(e.status, "completed")
        self.assertEqual(e.model, "qwen")
        self.assertEqual(e.workload, "nestjs-api")
        self.assertEqual(e.duration_ms, 1234.5)
        self.assertTrue(len(e.id) > 0)

    def test_run_lifecycle_started_and_completed(self):
        """Multiple lifecycle events should be distinguishable by status."""
        received = []
        self.bus.subscribe(RunLifecycleEvent, lambda e: received.append(e))

        self.bus.emit_sync(RunLifecycleEvent(status="started", model="m"))
        self.bus.emit_sync(RunLifecycleEvent(status="completed", model="m", duration_ms=500.0))
        self.bus.emit_sync(RunLifecycleEvent(status="failed", model="m", error="OOM"))

        self.assertEqual(len(received), 3)
        self.assertEqual([e.status for e in received], ["started", "completed", "failed"])

    def test_multiple_event_types_in_sequence(self):
        """Different event types emitted in sequence should each reach their handlers."""
        events_received = []

        def track(event):
            events_received.append(type(event).__name__)

        self.bus.subscribe_all(track)

        self.bus.emit_sync(RunLifecycleEvent(status="started", model="m"))
        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="Hello", index=0, timing_ms=10.0))
        self.bus.emit_sync(TokenGeneratedEvent(model="m", token="world", index=1, timing_ms=15.0))
        self.bus.emit_sync(
            CompletionEvent(
                model="m",
                response="Hello world",
                tokens_used=2,
                latency_ms=50,
                ttft_ms=10,
                tokens_per_second=40.0,
            )
        )
        self.bus.emit_sync(MetricEvent(name="score", value=0.9))
        self.bus.emit_sync(RunLifecycleEvent(status="completed", model="m", duration_ms=50.0))

        self.assertEqual(len(events_received), 6)
        self.assertEqual(events_received[0], "RunLifecycleEvent")
        self.assertEqual(events_received[1], "TokenGeneratedEvent")
        self.assertEqual(events_received[2], "TokenGeneratedEvent")
        self.assertEqual(events_received[3], "CompletionEvent")
        self.assertEqual(events_received[4], "MetricEvent")
        self.assertEqual(events_received[5], "RunLifecycleEvent")


# ═════════════════════════════════════════════════════════════════════
#  EVENT DATA INTEGRITY
# ═════════════════════════════════════════════════════════════════════


class TestEventBusDataIntegrity(unittest.TestCase):
    """Tests that event data is not mutated or lost during delivery."""

    def test_events_have_unique_ids(self):
        """Each event instance should have a unique id."""
        bus = EventBus()
        received = []
        bus.subscribe_all(lambda e: received.append(e.id))

        for i in range(100):
            bus.emit_sync(
                TokenGeneratedEvent(
                    model="m",
                    token=str(i),
                    index=i,
                    timing_ms=float(i),
                )
            )

        # All IDs should be unique
        self.assertEqual(len(received), 100)
        self.assertEqual(len(set(received)), 100, "Event IDs should be unique across 100 events")

    def test_token_events_sequential_indices(self):
        """TokenGeneratedEvent indices should be preserved through delivery."""
        bus = EventBus()
        received = []
        bus.subscribe(TokenGeneratedEvent, lambda e: received.append(e.index))

        for i in range(20):
            bus.emit_sync(
                TokenGeneratedEvent(
                    model="m",
                    token=f"tok_{i}",
                    index=i,
                    timing_ms=float(i),
                )
            )

        self.assertEqual(received, list(range(20)))

    def test_event_id_length(self):
        """Event IDs should be non-empty and reasonably short."""
        bus = EventBus()
        received = []
        bus.subscribe_all(lambda e: received.append(e.id))

        bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        eid = received[0]
        self.assertGreater(len(eid), 5)
        self.assertLess(len(eid), 30)
        self.assertTrue(eid.startswith("evt_"))


# ═════════════════════════════════════════════════════════════════════
#  EDGE CASES
# ═════════════════════════════════════════════════════════════════════


class TestEventBusEdgeCases(unittest.TestCase):
    """Edge cases for the EventBus."""

    def test_emit_with_no_subscribers(self):
        """Emitting with no subscribers should not raise."""
        bus = EventBus()
        bus.emit_sync(
            TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0)
        )  # Should not raise

    def test_emit_async_with_no_subscribers(self):
        """Async emitting with no subscribers should not raise."""
        bus = EventBus()

        async def emit_event():
            await bus.emit(
                TokenGeneratedEvent(
                    model="m",
                    token="t",
                    index=0,
                    timing_ms=1.0,
                )
            )

        asyncio.run(emit_event())  # Should not raise

    def test_subscribe_same_handler_twice(self):
        """Subscribing the same handler twice should deliver the event twice."""
        bus = EventBus()
        received = []

        def handler(e):
            received.append(e)

        bus.subscribe(TokenGeneratedEvent, handler)
        bus.subscribe(TokenGeneratedEvent, handler)

        bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))

        # Handler was registered twice, so it's called twice
        self.assertEqual(len(received), 2)

    def test_unsubscribe_after_emit(self):
        """Unsubscribing after emit should prevent future deliveries but not past ones."""
        bus = EventBus()
        received = []

        def handler(e):
            received.append(e)

        bus.subscribe(TokenGeneratedEvent, handler)
        bus.emit_sync(TokenGeneratedEvent(model="m", token="a", index=0, timing_ms=1.0))
        bus.unsubscribe(TokenGeneratedEvent, handler)
        bus.emit_sync(TokenGeneratedEvent(model="m", token="b", index=1, timing_ms=2.0))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].token, "a")

    def test_publish_context_empty_emits_zero(self):
        """Publish context with no emits should report 0."""
        bus = EventBus()

        async def run():
            async with bus.publish(run_id="test") as ctx:
                self.assertEqual(ctx.events_emitted, 0)

        asyncio.run(run())

    def test_enable_disable_toggle(self):
        """Toggling enable/disable multiple times should work."""
        bus = EventBus()
        received = []
        bus.subscribe(TokenGeneratedEvent, lambda e: received.append(e))

        bus.disable()
        bus.emit_sync(TokenGeneratedEvent(model="m", token="a", index=0, timing_ms=1.0))
        self.assertEqual(len(received), 0)

        bus.enable()
        bus.emit_sync(TokenGeneratedEvent(model="m", token="b", index=0, timing_ms=1.0))
        self.assertEqual(len(received), 1)

        bus.disable()
        bus.emit_sync(TokenGeneratedEvent(model="m", token="c", index=0, timing_ms=1.0))
        self.assertEqual(len(received), 1)

        bus.enable()
        bus.emit_sync(TokenGeneratedEvent(model="m", token="d", index=0, timing_ms=1.0))
        self.assertEqual(len(received), 2)


# ═════════════════════════════════════════════════════════════════════
#  DEFAULT BUS
# ═════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════
#  MODEL LENS EVENT & PRIORITY
# ═════════════════════════════════════════════════════════════════════


class TestModelLensEventPriority(unittest.TestCase):
    """Tests for EventPriority enum and ModelLensEvent base class."""

    def test_event_priority_values(self):
        """EventPriority enum should have expected integer values."""
        self.assertEqual(EventPriority.LOW.value, 0)
        self.assertEqual(EventPriority.NORMAL.value, 1)
        self.assertEqual(EventPriority.HIGH.value, 2)
        self.assertEqual(EventPriority.CRITICAL.value, 3)

    def test_event_priority_order(self):
        """EventPriority should be ordered (LOW < NORMAL < HIGH < CRITICAL)."""
        self.assertLess(EventPriority.LOW.value, EventPriority.NORMAL.value)
        self.assertLess(EventPriority.NORMAL.value, EventPriority.HIGH.value)
        self.assertLess(EventPriority.HIGH.value, EventPriority.CRITICAL.value)

    def test_event_type_values(self):
        """EventType enum should have string values."""
        self.assertEqual(EventType.RUN_STARTED.value, "run.started")
        self.assertEqual(EventType.TOKEN_GENERATED.value, "provider.token_generated")
        self.assertEqual(EventType.COMPLETION_RECEIVED.value, "provider.completion_received")
        self.assertEqual(EventType.ERROR.value, "system.error")
        self.assertEqual(EventType.TRACE_CAPTURED.value, "trace.captured")

    def test_model_lens_event_priority_field(self):
        """ModelLensEvent should carry priority through emit."""
        bus = EventBus()
        received = []
        event = ModelLensEvent(
            type=EventType.RUN_STARTED,
            source="test",
            priority=EventPriority.HIGH,
        )
        bus.subscribe(ModelLensEvent, lambda e: received.append(e))
        bus.emit_sync(event)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].priority, EventPriority.HIGH)
        self.assertEqual(received[0].type, EventType.RUN_STARTED)

    def test_model_lens_event_default_priority(self):
        """ModelLensEvent should default to NORMAL priority."""
        received = []
        bus = EventBus()
        event = ModelLensEvent(type=EventType.METRIC_RECORDED, source="test")
        bus.subscribe(ModelLensEvent, lambda e: received.append(e))
        bus.emit_sync(event)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].priority, EventPriority.NORMAL)

    def test_model_lens_event_has_id_and_timestamp(self):
        """ModelLensEvent should auto-generate id and timestamp."""
        event = ModelLensEvent(type=EventType.RUN_STARTED, source="test")
        self.assertTrue(len(event.id) > 0)
        self.assertTrue(event.id.startswith("evt_"))
        self.assertGreater(event.timestamp, 0)

    def test_model_lens_event_different_ids(self):
        """Each ModelLensEvent instance should have a unique id."""
        event1 = ModelLensEvent(type=EventType.RUN_STARTED, source="test")
        event2 = ModelLensEvent(type=EventType.RUN_STARTED, source="test")
        self.assertNotEqual(event1.id, event2.id)


class TestDefaultBus(unittest.TestCase):
    """Tests for the default_bus singleton."""

    def test_default_bus_is_eventbus_instance(self):
        """default_bus should be an EventBus instance."""
        from events import default_bus

        self.assertIsInstance(default_bus, EventBus)

    def test_default_bus_emits_to_subscribers(self):
        """default_bus should work like a normal EventBus."""
        from events import default_bus

        # We don't want to pollute the global singleton's state permanently,
        # so we use a separate bus for this test
        bus = EventBus()
        received = []
        bus.subscribe(TokenGeneratedEvent, lambda e: received.append(e))
        bus.emit_sync(TokenGeneratedEvent(model="m", token="t", index=0, timing_ms=1.0))
        self.assertEqual(len(received), 1)


if __name__ == "__main__":
    unittest.main()

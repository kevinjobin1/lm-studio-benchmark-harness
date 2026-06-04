"""Unit tests for EventBusSSEServer._forward_to_worker with ThreadPoolExecutor.

Verifies that the shared thread pool is used instead of spawning
a new daemon thread per event, and that the pool shuts down cleanly.

NOTE: This file is separate from test_events.py because importing
asyncio / concurrent.futures at module level triggers a circular
import in packages/logging.py (which shadows the stdlib 'logging'
module). We avoid that by deferring heavy imports to test methods.
"""

import json
import unittest
from unittest.mock import patch, MagicMock


class TestSSEForwardToWorker(unittest.TestCase):
    """Tests for EventBusSSEServer._forward_to_worker with ThreadPoolExecutor."""

    def setUp(self):
        from events import EventBus

        self.bus = EventBus()
        self._server = None

    def tearDown(self):
        if self._server is not None and hasattr(self._server, "_worker_forwarder"):
            pool = getattr(self._server, "_worker_forwarder", None)
            if pool is not None:
                try:
                    pool.shutdown(wait=False)
                except Exception:
                    pass

    def _make_server(self, **kwargs):
        """Create a server, tracking it for tearDown cleanup."""
        from events.sse import EventBusSSEServer

        self._server = EventBusSSEServer(bus=self.bus, **kwargs)
        return self._server

    # ── Pool creation ──────────────────────────────────────────────

    def test_pool_created_when_worker_url_is_set(self):
        server = self._make_server(worker_url="https://example.com/events")
        self.assertIsNotNone(server._worker_forwarder)
        # ThreadPoolExecutor class name check (avoids module-level import)
        self.assertEqual(type(server._worker_forwarder).__name__, "ThreadPoolExecutor")

    def test_pool_not_created_when_worker_url_is_none(self):
        server = self._make_server(worker_url=None)
        self.assertIsNone(server._worker_forwarder)

    def test_pool_not_created_when_worker_url_is_empty(self):
        server = self._make_server(worker_url="")
        self.assertIsNone(server._worker_forwarder)

    def test_pool_reads_worker_url_from_env(self):
        with patch.dict("os.environ", {"MODELLENS_SSE_WORKER_URL": "https://env.example.com"}):
            server = self._make_server()
            self.assertEqual(server.worker_url, "https://env.example.com")
            self.assertIsNotNone(server._worker_forwarder)

    # ── Pool submission ────────────────────────────────────────────

    def test_forward_to_worker_submits_to_pool(self):
        server = self._make_server(worker_url="https://bridge.example.com")
        # Shut down the real pool before replacing with a mock
        server._worker_forwarder.shutdown(wait=False)

        mock_pool = MagicMock()
        server._worker_forwarder = mock_pool

        data = {"_event_type": "TokenGeneratedEvent", "model": "test", "token": "hi"}
        server._forward_to_worker(data)

        mock_pool.submit.assert_called_once()
        args, _ = mock_pool.submit.call_args
        self.assertEqual(len(args), 1)
        self.assertTrue(callable(args[0]))

    def test_forward_to_worker_skips_when_pool_is_none(self):
        server = self._make_server(worker_url=None)
        server._forward_to_worker({"_event_type": "TokenGeneratedEvent"})
        # Did not raise — pool is None, guard clause returned early
        self.assertIsNone(server._worker_forwarder)

    # ── HTTP request construction ──────────────────────────────────

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_forward_task_posts_to_correct_url(self, mock_request_class, mock_urlopen):
        server = self._make_server(worker_url="https://bridge.example.com/")
        data = {"_event_type": "TokenGeneratedEvent", "model": "qwen", "token": "abc"}

        server._forward_to_worker(data)
        server._worker_forwarder.shutdown(wait=True)

        mock_request_class.assert_called_once()
        args, kwargs = mock_request_class.call_args
        self.assertEqual(args[0], "https://bridge.example.com/events")
        self.assertEqual(
            kwargs.get("data"),
            b'{"_event_type": "TokenGeneratedEvent", "model": "qwen", "token": "abc"}',
        )
        self.assertEqual(
            kwargs.get("headers"),
            {"Content-Type": "application/json", "User-Agent": "modellens/0.1"},
        )
        self.assertEqual(kwargs.get("method"), "POST")
        mock_urlopen.assert_called_once()

    # ── Error handling ─────────────────────────────────────────────

    @patch("urllib.request.urlopen")
    def test_forward_errors_are_silently_ignored(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        server = self._make_server(worker_url="https://unreachable.example.com")

        # Should not raise
        server._forward_to_worker({"_event_type": "TokenGeneratedEvent"})
        server._worker_forwarder.shutdown(wait=True)

        mock_urlopen.assert_called_once()

    # ── Closure semantics ──────────────────────────────────────────

    @patch("urllib.request.urlopen")
    def test_closure_captures_payload_by_value(self, mock_urlopen):
        """Mutating the caller's dict after submit must not affect forwarded data.

        _forward_to_worker captures url and the serialized payload (bytes) in
        local variables before defining the _post closure.  Mutating the
        caller's data dict after submit should leave the first POST payload
        untouched.
        """
        server = self._make_server(worker_url="https://bridge.example.com")

        data = {"_event_type": "TokenGeneratedEvent", "token": "original"}
        server._forward_to_worker(data)

        data["token"] = "mutated"
        data["extra"] = "injected"
        server._forward_to_worker(data)

        server._worker_forwarder.shutdown(wait=True)
        self.assertEqual(mock_urlopen.call_count, 2)

        # urlopen receives the real Request objects; read their .data bytes
        calls = mock_urlopen.call_args_list
        first_payload = json.loads(calls[0].args[0].data)
        second_payload = json.loads(calls[1].args[0].data)

        self.assertEqual(first_payload["token"], "original")
        self.assertNotIn("extra", first_payload)

        self.assertEqual(second_payload["token"], "mutated")
        self.assertIn("extra", second_payload)

    # ── Pool lifecycle / shutdown ──────────────────────────────────

    def test_stop_shuts_down_pool_without_waiting(self):
        server = self._make_server(worker_url="https://example.com")
        server._worker_forwarder.shutdown(wait=False)

        mock_pool = MagicMock()
        server._worker_forwarder = mock_pool

        server.stop()

        mock_pool.shutdown.assert_called_once_with(wait=False)
        self.assertIsNone(server._worker_forwarder)

    def test_stop_handles_missing_pool_gracefully(self):
        server = self._make_server(worker_url=None)
        server.stop()  # Must not raise

    # ── Pool reuse ─────────────────────────────────────────────────

    @patch("urllib.request.urlopen")
    def test_multiple_events_reuse_same_pool(self, mock_urlopen):
        server = self._make_server(worker_url="https://example.com")
        pool_id = id(server._worker_forwarder)

        for i in range(10):
            server._forward_to_worker({"_event_type": "Test", "index": i})

        self.assertEqual(id(server._worker_forwarder), pool_id)
        server._worker_forwarder.shutdown(wait=True)
        self.assertEqual(mock_urlopen.call_count, 10)


    # ── URL construction edge cases ────────────────────────────────

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_no_trailing_slash(self, mock_request_class, mock_urlopen):
        """worker_url without trailing slash → /events appended cleanly."""
        server = self._make_server(worker_url="https://bridge.example.com")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://bridge.example.com/events",
        )

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_trailing_slash(self, mock_request_class, mock_urlopen):
        """worker_url with trailing slash → only one slash before 'events'."""
        server = self._make_server(worker_url="https://bridge.example.com/")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://bridge.example.com/events",
        )

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_multiple_trailing_slashes(self, mock_request_class, mock_urlopen):
        """worker_url with multiple trailing slashes → all stripped."""
        server = self._make_server(worker_url="https://bridge.example.com///")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://bridge.example.com/events",
        )

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_with_path_segment(self, mock_request_class, mock_urlopen):
        """worker_url with a path segment → /events appended after it."""
        server = self._make_server(worker_url="https://example.com/api/bridge")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://example.com/api/bridge/events",
        )

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_path_with_trailing_slash(self, mock_request_class, mock_urlopen):
        """worker_url with path + trailing slash → clean /events suffix."""
        server = self._make_server(worker_url="https://example.com/api/bridge/")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://example.com/api/bridge/events",
        )

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_query_params_stripped(self, mock_request_class, mock_urlopen):
        """Query params in worker_url are stripped before appending /events.

        Uses urllib.parse.urlparse to decompose the URL, drop query and
        fragment, then recompose before rstrip + /events.
        """
        server = self._make_server(worker_url="https://bridge.example.com?token=abc")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://bridge.example.com/events",
        )

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_fragment_stripped(self, mock_request_class, mock_urlopen):
        """URL fragments (#section) are stripped before appending /events."""
        server = self._make_server(worker_url="https://bridge.example.com#main")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://bridge.example.com/events",
        )

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_url_query_and_fragment_stripped(self, mock_request_class, mock_urlopen):
        """Both query params AND fragments are stripped."""
        server = self._make_server(worker_url="https://bridge.example.com?t=1#s")
        server._forward_to_worker({"_event_type": "Test"})
        server._worker_forwarder.shutdown(wait=True)
        mock_request_class.assert_called_once()
        self.assertEqual(
            mock_request_class.call_args[0][0],
            "https://bridge.example.com/events",
        )


if __name__ == "__main__":
    unittest.main()
